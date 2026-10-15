# Bite-proof record: the simple ruling window (C7 L2b, Canon 2026-10-15-dcc2b5e5-3)

Guards of `round_driver.py` (`_cmd_rule_locked`, `_resolve_ruled_batch`, `_queue_fix_batch`) proven by
`plugins/superheroes/lib/tests/test_ruling_window_c7.py`. This record replaces the earlier one, whose
elements guarded code the Canon ruling removed (`withdraw`, the timing refusals, the autonomous lift,
the carry/re-join paths).

Method, per element: one targeted string edit of `round_driver.py` (the neutralization, quoted);
the detector node run alone, unedited (`-q -n 0`, never a filtered suite log); the inverse edit
(the restore, quoted back); the same node run again. `sha256` of `round_driver.py` (first 16 hex
digits) is `d82357d35b914254` before every neutralization and after every restore, so each restore
returned the file byte for byte. Raw outputs are verbatim from the runs; temporary directory names
(`/tmp/claude-0/pytest-of-root/...`) are the only environment detail in them.

Guarded-element set (declared by this record; the order named elements i-vi):

1. i — `rule` never refuses for timing (`_cmd_rule_locked`)
2. ii — the resolution point attaches a ruling to the row it binds (`ruledBy`, `_resolve_ruled_batch`)
3. iii — the resolution point adds an owner-named finding no fixer was sent (`added.append`)
4. iv — it does not send a decision again (`sentUnderDecision` compare)
5. v — it restages a finding fixed against a later ruling (`_reopened_ledger_row`)
6. vi — no autonomous lift (`_queue_fix_batch` offers only blockers and owner-named rows)
7. vii — a ruling never reshapes a fixer attempt whose orders are out (`if not emitted:` in `rule`)

Unproven (no neutralization run; the order's budget allowed 14 bite-proof runs = 7 elements):
the "ruling names no live finding" line and dispatch-nothing edge (`_ruled_row` returning
`(None, False)`; covered by `test_a_ruling_naming_no_live_finding_dispatches_nothing_and_is_recorded`),
and the single-writer census (`test_every_fixer_batch_passes_the_one_resolution_point`).

## Element i. `rule` never refuses for timing

- **Guarded element:** `round_driver.py` `_cmd_rule_locked`, after `emitted = (...)`. Axis: REFUSAL — a ruling is recorded whichever step is pending, with the fixer orders already out.
- **Detector (run alone):** `test_ruling_window_c7.py::test_vet_442_ruling_on_an_emitted_order_is_accepted_and_reaches_the_next_order`

**Neutralization.** Inserted after the `emitted = (...)` statement:

```python
    if emitted:
        return _refuse_cmd(session_dir, RULE_CMD, "ruling-attempt-pending", phase=P_FIXER)
```

**Raw red** (exit 1):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_vet_442_ruling_on_an_emitted_order_is_accepted_and_reaches_the_next_order _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-15/test_vet_442_ruling_on_an_emit0')
keep_severity = None

    def test_vet_442_ruling_on_an_emitted_order_is_accepted_and_reaches_the_next_order(
            tmp_path, keep_severity):
        """axis: REFUSAL — a `guidance` ruling on a finding in the batch of a fixer order that is already
        out is recorded (no `ruling-attempt-pending`), the attempt and its batch are left as they were,
        the fixer's result folds normally, and the next fixer order carries the finding with the guidance.
        """
        session_dir, gitdir, head_path, key_a, key_b = _two_important(tmp_path, "c7-442")
        emitted = _state(session_dir)
        assert RD._journal_has_orders_emitted(
            session_dir, emitted["round"], P_FIXER, emitted["pending"]["attempt"])
        assert "TAKE-THE-SECOND-OPTION" not in _order_text(session_dir)
    
        out = _rule(session_dir, _guidance_file(tmp_path, "r.json", key_a, "TAKE-THE-SECOND-OPTION"))
>       assert out.get("ok") is True, out
E       AssertionError: {'ok': False, 'reason': 'ruling-attempt-pending'}
E       assert False is True
E        +  where False = <built-in method get of dict object at 0x7f426d9a4b80>('ok')
E        +    where <built-in method get of dict object at 0x7f426d9a4b80> = {'ok': False, 'reason': 'ruling-attempt-pending'}.get

/home/user/wt-l2b/plugins/superheroes/lib/tests/test_ruling_window_c7.py:158: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_ruling_window_c7.py::test_vet_442_ruling_on_an_emitted_order_is_accepted_and_reaches_the_next_order
1 failed in 1.86s
```

**Restore.** Inverse edit: the two inserted lines removed. Restored lines (`round_driver.py:7521-7524`):

```python
    emitted = (isinstance(pending, dict) and pending.get("phase") == P_FIXER
               and _journal_has_orders_emitted(session_dir, pending.get("round"), P_FIXER,
                                               pending.get("attempt")))
    cfg = state.get("config") or {}
```

Restore receipt: `sha256(round_driver.py)` first 16 hex digits `d82357d35b914254` before the neutralization and after the restore.

**Raw green** (exit 0):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 13.96s
```

## Element ii. the resolution point attaches a ruling to its row

- **Guarded element:** `round_driver.py` `_resolve_ruled_batch`, the `ruledBy` stamp. Axis: ATTACH — guidance given to a finding merged into another renders on the representative the fixer is sent.
- **Detector (run alone):** `test_ruling_window_c7.py::test_a_ruling_on_a_member_merged_into_another_reaches_the_one_live_row`

**Neutralization.** Replaced `row["ruledBy"] = decision["findingKey"]  # a ruling given to a merged-in finding` with `pass  # a ruling given to a merged-in finding`.

**Raw red** (exit 1):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_a_ruling_on_a_member_merged_into_another_reaches_the_one_live_row ____

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-17/test_a_ruling_on_a_member_merg0')
keep_severity = None

    def test_a_ruling_on_a_member_merged_into_another_reaches_the_one_live_row(
            tmp_path, keep_severity):
        """axis: ATTACH — guidance given on a finding merged into another binds the representative: the
        representative is the row the next fixer order carries, with the member's guidance on it.
    
        bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo1b_c7_ruling_window.md (element 2)
        """
        session_dir, gitdir, head_path, member, kept = _merged_into_session(tmp_path)
        assert _rule(session_dir, _guidance_file(tmp_path, "g.json", member, "FOR-THE-MERGED"))["ok"]
        _drive_one_phase(session_dir, gitdir, [], head_path)
        state = _drive_until(session_dir, gitdir, head_path, P_FIXER)
        assert state["round"] == 2
        assert _batch_keys(state) == [kept] and _offered(state, session_dir, kept)
        assert member not in _batch_keys(state)
>       assert "FOR-THE-MERGED" in _order_text(session_dir)
E       AssertionError: assert 'FOR-THE-MERGED' in 'You are the fixer for one round of an auto-fix code-review loop.\n\n## Input\n- Findings to fix: /tmp/claude-0/pytest...st-17/test_a_ruling_on_a_member_merg0/c7-merge/round-2/landing/dispatch-fixer/fixer-508e7896192355de.a0.payload.json\n'
E        +  where 'You are the fixer for one round of an auto-fix code-review loop.\n\n## Input\n- Findings to fix: /tmp/claude-0/pytest...st-17/test_a_ruling_on_a_member_merg0/c7-merge/round-2/landing/dispatch-fixer/fixer-508e7896192355de.a0.payload.json\n' = _order_text('/tmp/claude-0/pytest-of-root/pytest-17/test_a_ruling_on_a_member_merg0/c7-merge')

/home/user/wt-l2b/plugins/superheroes/lib/tests/test_ruling_window_c7.py:414: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_ruling_window_c7.py::test_a_ruling_on_a_member_merged_into_another_reaches_the_one_live_row
1 failed in 3.23s
```

**Restore.** Inverse edit. Restored line (`round_driver.py:4530`):

```python
            row["ruledBy"] = decision["findingKey"]  # a ruling given to a merged-in finding
```

Restore receipt: `sha256(round_driver.py)` first 16 hex digits `d82357d35b914254` before the neutralization and after the restore.

**Raw green** (exit 0):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 2.55s
```

## Element iii. the resolution point adds an owner-named finding no fixer was sent

- **Guarded element:** `round_driver.py` `_resolve_ruled_batch`, `added.append(row)`. Axis: OWNER-NAMED, WHATEVER THE SEVERITY — a code-quality Minor named by `guidance` reaches the next fixer.
- **Detector (run alone):** `test_ruling_window_c7.py::test_a_minor_named_by_guidance_reaches_the_next_fixer`

**Neutralization.** Replaced the statement `added.append(row)` (followed by `added.sort(`) with `pass`.

**Raw red** (exit 1):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_a_minor_named_by_guidance_reaches_the_next_fixer _____________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-19/test_a_minor_named_by_guidance0')
keep_severity = None

    def test_a_minor_named_by_guidance_reaches_the_next_fixer(tmp_path, keep_severity):
        """axis: OWNER-NAMED, WHATEVER THE SEVERITY — a code-quality Minor that was never in a fix batch,
        named by a `guidance` ruling while the blocker's fixer is out, rides the next fixer order with the
        guidance, and nothing else below blocking does.
    
        bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo1b_c7_ruling_window.md (element 3)
        """
        session_dir, gitdir, head_path = _session(
            tmp_path, [_finding("blocker B", 1),
                       _finding("real minor", 2, "Minor", "real"),
                       _finding("quality minor", 3, "Minor", "code-quality")], name="c7-minor")
        state = _state(session_dir)
        assert [r["title"] for r in state["_fixBatch"]] == ["blocker B"]
        key_q = _finding_key_by_title(state, "quality minor")
        assert _rule(session_dir, _guidance_file(tmp_path, "g.json", key_q, "TIDY-THE-NAMES"))["ok"]
        _drive_one_phase(session_dir, gitdir, [], head_path)
>       state = _drive_until(session_dir, gitdir, head_path, P_FIXER)
                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

/home/user/wt-l2b/plugins/superheroes/lib/tests/test_ruling_window_c7.py:337: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

session_dir = '/tmp/claude-0/pytest-of-root/pytest-19/test_a_minor_named_by_guidance0/c7-minor'
gitdir = '/tmp/claude-0/pytest-of-root/pytest-19/test_a_minor_named_by_guidance0/c7-minor-gitdir'
head_path = '/tmp/claude-0/pytest-of-root/pytest-19/test_a_minor_named_by_guidance0/c7-minor-head.diff'
phase = 'dispatch-fixer', max_steps = 12

    def _drive_until(session_dir, gitdir, head_path, phase, max_steps=12):
        """Drive pending phases (no new panel findings) until `phase` is pending."""
        for _ in range(max_steps):
            state = _state(session_dir)
>           assert not state.get("terminal"), state.get("terminal")
E           AssertionError: converged
E           assert not 'converged'
E            +  where 'converged' = <built-in method get of dict object at 0x7f8fe85b5640>('terminal')
E            +    where <built-in method get of dict object at 0x7f8fe85b5640> = {'_advanceUsed': True, '_auditOutcome': {'ambiguous': [], 'audits': [{'auditor': 'codex', 'classKey': 'code-reviewer::...r::::blocker b', 'dimension': 'code-reviewer', 'evidence': 'read src/f00.py', ...}], '_changedSubjects': ['Code'], ...}.get

/home/user/wt-l2b/plugins/superheroes/lib/tests/test_ruling_window_c7.py:114: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_ruling_window_c7.py::test_a_minor_named_by_guidance_reaches_the_next_fixer
1 failed in 2.11s
```

**Restore.** Inverse edit. Restored line (`round_driver.py:4518`):

```python
        added.append(row)
```

Restore receipt: `sha256(round_driver.py)` first 16 hex digits `d82357d35b914254` before the neutralization and after the restore.

**Raw green** (exit 0):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 2.57s
```

## Element iv. the resolution point does not send a decision again

- **Guarded element:** `round_driver.py` `_resolve_ruled_batch`, the `sentUnderDecision` compare. Axis: NO REPEAT — a finding sent under a ruling is not sent again under it; a newer ruling sends it once more.
- **Detector (run alone):** `test_ruling_window_c7.py::test_a_decision_already_sent_is_not_sent_again`

**Neutralization.** Replaced `or sent.get(_lineage_root(lineage, decision["findingKey"]), -1) >= decision["seq"]):` with `or False):`.

**Raw red** (exit 1):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
________________ test_a_decision_already_sent_is_not_sent_again ________________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-21/test_a_decision_already_sent_i0')
keep_severity = None

    def test_a_decision_already_sent_is_not_sent_again(tmp_path, keep_severity):
        """axis: NO REPEAT — a finding sent to a fixer under a ruling is not sent again under that same
        ruling in any later round; a newer ruling on it is.
    
        bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo1b_c7_ruling_window.md (element 4)
        """
        session_dir, gitdir, head_path, key_a, _key_b = _two_important(tmp_path, "c7-once")
        assert _rule(session_dir, _guidance_file(tmp_path, "g1.json", key_a, "FIRST"))["ok"]
        _drive_one_phase(session_dir, gitdir, [], head_path)
        state = _drive_until(session_dir, gitdir, head_path, P_FIXER)
        assert state["round"] == 2 and _offered(state, session_dir, key_a)
        # round 2's fixer folds and its audit discharges A again: with no newer ruling, the loop converges
>       _sent, state = _run_recording_fixer_batches(session_dir, gitdir, head_path)
                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

/home/user/wt-l2b/plugins/superheroes/lib/tests/test_ruling_window_c7.py:447: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

session_dir = '/tmp/claude-0/pytest-of-root/pytest-21/test_a_decision_already_sent_i0/c7-once'
gitdir = '/tmp/claude-0/pytest-of-root/pytest-21/test_a_decision_already_sent_i0/c7-once-gitdir'
head_path = '/tmp/claude-0/pytest-of-root/pytest-21/test_a_decision_already_sent_i0/c7-once-head.diff'
max_steps = 30

    def _run_recording_fixer_batches(session_dir, gitdir, head_path, max_steps=30):
        """Drive to the terminal; the titles of every fixer batch the driver sent, in order."""
        sent = []
        for _ in range(max_steps):
            state = _state(session_dir)
            if state.get("terminal"):
                return sent, state
            if state["pending"]["phase"] == P_FIXER:
                sent.append([r["title"] for r in state["_fixBatch"]])
>               assert len(sent) <= 3, "a fixer was sent out again and again: %s" % sent
E               AssertionError: a fixer was sent out again and again: [['bounds F'], ['bounds F'], ['bounds F'], ['bounds F']]
E               assert 4 <= 3
E                +  where 4 = len([['bounds F'], ['bounds F'], ['bounds F'], ['bounds F']])

/home/user/wt-l2b/plugins/superheroes/lib/tests/test_ruling_window_c7.py:290: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_ruling_window_c7.py::test_a_decision_already_sent_is_not_sent_again
1 failed in 3.79s
```

**Restore.** Inverse edit. Restored line (`round_driver.py:4499`):

```python
                or sent.get(_lineage_root(lineage, decision["findingKey"]), -1) >= decision["seq"]):
```

Restore receipt: `sha256(round_driver.py)` first 16 hex digits `d82357d35b914254` before the neutralization and after the restore.

**Raw green** (exit 0):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 5.54s
```

## Element v. it restages a finding fixed against a later ruling

- **Guarded element:** `round_driver.py` `_reopened_ledger_row`. Axis: RESTAGE — a finding the fix archived as fixed comes back in the next round's fixer order with the ruling; the resolver does not write the ledger (the restage is marked in driver state, `restagedAfterDispositionSeq`, and the ledger keeps its fold-time record).
- **Detector (run alone):** `test_ruling_window_c7.py::test_a_fix_that_went_against_the_ruling_is_sent_back_restaged`
- **Re-recorded** after `c7-l2b-wo-census2`: the resolver no longer drops the disposition in the ledger, so `_reopened_ledger_row` now returns the row for the restage and `sha256(round_driver.py)` (first 16 hex digits) is `6d229dd833dbaef7` before the neutralization and after the restore.

**Neutralization.** Inserted `    return None` as the statement after the docstring of `_reopened_ledger_row`.

**Raw red** (exit 1):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_a_fix_that_went_against_the_ruling_is_sent_back_restaged _________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-40/test_a_fix_that_went_against_t0')
keep_severity = None

    def test_a_fix_that_went_against_the_ruling_is_sent_back_restaged(tmp_path, keep_severity):
        """axis: RESTAGE — A is in an emitted order, the ruling arrives, the fix lands and A is archived as
        fixed; the next round's fixer order still carries A with the ruling (the restage lives in driver
        state; the ledger keeps its fold-time record).
    
        bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo1b_c7_ruling_window.md (element 5)
        """
        session_dir, gitdir, head_path, key_a, _key_b = _two_important(tmp_path, "c7-restage")
        assert _rule(session_dir, _guidance_file(tmp_path, "g.json", key_a, "DO-NOT-DELETE-IT"))["ok"]
        _drive_one_phase(session_dir, gitdir, [], head_path)  # the fixer folds
        _drive_one_phase(session_dir, gitdir, [], head_path)  # the audit discharges A
        state = _state(session_dir)
        assert _ledger_row(state, key_a)["disposition"] == "fixed"
    
>       state = _drive_until(session_dir, gitdir, head_path, P_FIXER)
                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

/home/user/wt-l2b/plugins/superheroes/lib/tests/test_ruling_window_c7.py:272: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

session_dir = '/tmp/claude-0/pytest-of-root/pytest-40/test_a_fix_that_went_against_t0/c7-restage'
gitdir = '/tmp/claude-0/pytest-of-root/pytest-40/test_a_fix_that_went_against_t0/c7-restage-gitdir'
head_path = '/tmp/claude-0/pytest-of-root/pytest-40/test_a_fix_that_went_against_t0/c7-restage-head.diff'
phase = 'dispatch-fixer', max_steps = 12

    def _drive_until(session_dir, gitdir, head_path, phase, max_steps=12):
        """Drive pending phases (no new panel findings) until `phase` is pending."""
        for _ in range(max_steps):
            state = _state(session_dir)
>           assert not state.get("terminal"), state.get("terminal")
E           AssertionError: converged
E           assert not 'converged'
E            +  where 'converged' = <built-in method get of dict object at 0x7ff91085f7c0>('terminal')
E            +    where <built-in method get of dict object at 0x7ff91085f7c0> = {'_advanceUsed': True, '_auditOutcome': {'ambiguous': [], 'audits': [{'auditor': 'codex', 'classKey': 'code-reviewer::...er::::bounds g', 'dimension': 'code-reviewer', 'evidence': 'read src/f00.py', ...}], '_changedSubjects': ['Code'], ...}.get

/home/user/wt-l2b/plugins/superheroes/lib/tests/test_ruling_window_c7.py:114: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_ruling_window_c7.py::test_a_fix_that_went_against_the_ruling_is_sent_back_restaged
1 failed in 2.69s
```

**Restore.** Inverse edit (removed the inserted `return None`). Restored lines (`round_driver.py:4451-4455`):

```python
def _reopened_ledger_row(ledger_by_key, key):
    """The finding's own ledger row as an open finding again (its disposition dropped), or None."""
    row = ledger_by_key.get(key)
    if not isinstance(row, dict):
        return None
```

Restore receipt: `sha256(round_driver.py)` first 16 hex digits `6d229dd833dbaef7` before the neutralization and after the restore.

**Raw green** (exit 0):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 2.71s
```

## Element vi. no autonomous lift

- **Guarded element:** `round_driver.py` `_queue_fix_batch`, directly after `filtered = _resolve_ruled_batch(state, filtered)`. Axis: NO AUTONOMOUS LIFT — a below-blocking finding no ruling names never rides a fix batch; it is settled at convergence.
- **Detector (run alone):** `test_ruling_window_c7.py::test_a_converged_loop_settles_its_minors_and_never_puts_them_in_a_fix_batch`

**Neutralization.** Inserted, after that line, a re-creation of the removed lift (every live real-consequence non-blocking finding joins a batch that is going out):

```python
    if filtered:
        filtered += [dict(f) for f in state.get("findings") or [] if isinstance(f, dict)
                     and f.get("consequenceKind") == "real" and not circuit_breaker.is_blocking(f.get("severity"))
                     and _fix_batch_row_key(f) not in {_fix_batch_row_key(r) for r in filtered}]
```

**Raw red** (exit 1):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_converged_loop_settles_its_minors_and_never_puts_them_in_a_fix_batch __

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-25/test_a_converged_loop_settles_0')
keep_severity = None

    def test_a_converged_loop_settles_its_minors_and_never_puts_them_in_a_fix_batch(
            tmp_path, keep_severity):
        """axis: NO AUTONOMOUS LIFT — a real-consequence Minor and a code-quality Minor, neither ruled,
        ride no fixer batch; at convergence the first is left for the owner with its consequence and the
        second is craft, and the session's left-for-owner count (what the review record names) is 1.
    
        bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo1b_c7_ruling_window.md (element 6)
        """
        import review_record_session
        session_dir, gitdir, head_path = _session(
            tmp_path, [_finding("blocker B", 1),
                       _finding("real minor", 2, "Minor", "real"),
                       _finding("quality minor", 3, "Minor", "code-quality")], name="c7-settle")
        sent, state = _run_recording_fixer_batches(session_dir, gitdir, head_path)
        assert state["terminal"] == "converged"
>       assert sent and all(titles == ["blocker B"] for titles in sent), sent
E       AssertionError: [['blocker B', 'real minor']]
E       assert ([['blocker B', 'real minor']] and False)
E        +  where False = all(<generator object test_a_converged_loop_settles_its_minors_and_never_puts_them_in_a_fix_batch.<locals>.<genexpr> at 0x7f22acb27b90>)

/home/user/wt-l2b/plugins/superheroes/lib/tests/test_ruling_window_c7.py:311: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_ruling_window_c7.py::test_a_converged_loop_settles_its_minors_and_never_puts_them_in_a_fix_batch
1 failed in 2.02s
```

**Restore.** Inverse edit: the four inserted lines removed. Restored lines (`round_driver.py:4568-4570`):

```python
    filtered = _resolve_ruled_batch(state, filtered)
    if not filtered and not offered_nonempty:
        return "empty"
```

Restore receipt: `sha256(round_driver.py)` first 16 hex digits `d82357d35b914254` before the neutralization and after the restore.

**Raw green** (exit 0):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 1.91s
```

## Element vii. a ruling never reshapes a fixer attempt whose orders are out

- **Guarded element:** `round_driver.py` `_cmd_rule_locked`, the `if not emitted:` before `_reconcile_fixer_queue_after_rulings`. Axis: NON-INTERFERENCE — the pending attempt, `_fixBatch`, `_fixQueue` and `fix-batch.json` stay as they were.
- **Detector (run alone):** `test_ruling_window_c7.py::test_a_ruling_on_a_row_in_the_emitted_order_leaves_the_attempt_untouched`

**Neutralization.** Replaced `    if not emitted:` (directly above `_reconcile_fixer_queue_after_rulings(`) with `    if True:`.

**Raw red** (exit 1):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_a_ruling_on_a_row_in_the_emitted_order_leaves_the_attempt_untouched ___

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-27/test_a_ruling_on_a_row_in_the_0')
keep_severity = None

    def test_a_ruling_on_a_row_in_the_emitted_order_leaves_the_attempt_untouched(
            tmp_path, keep_severity):
        """axis: NON-INTERFERENCE — an `out-of-scope` ruling on a row of the emitted batch is recorded but
        the pending attempt, `_fixBatch`, `_fixQueue` and the emitted `fix-batch.json` stay byte-identical
        (a fix under way is never stopped or re-sliced)."""
        session_dir, _g, _h, key_a, _key_b = _two_important(tmp_path, "c7-untouched")
        before = _state(session_dir)
        path = os.path.join(RR.round_dir(session_dir, before["round"]), "fix-batch.json")
        with open(path, "rb") as fh:
            file_before = fh.read()
        out = _rule(session_dir, _write_ruling_file(tmp_path / "r.json", [
            {"id": key_a, "ruling": "out-of-scope", "reason": "later", "followUp": _follow_up()}]))
        assert out.get("ok") is True, out
        after = _state(session_dir)
        for field in ("pending", "_fixBatch", "_fixQueue", "_fixBatchIndex"):
>           assert after.get(field) == before.get(field), field
E           AssertionError: pending
E           assert {'action': 'd...h-fixer', ...} == {'action': 'd...h-fixer', ...}
E             
E             Omitting 4 identical items, use -vv to show
E             Differing items:
E             {'payload': {'batch': [{'classification': 'mechanical', 'consequence': 'a reviewer-found defect stays in the change', 'consequenceKind': 'real', 'detail': 'bounds G at src/f00.py:2', ...}]}} != {'payload': {'batch': [{'classification': 'mechanical', 'consequence': 'a reviewer-found defect stays in the change', ...'a reviewer-found defect stays in the change', 'consequenceKind': 'real', 'detail': 'bounds G at src/f00.py:2', ...}]}}
E             Use -v to get more diff

/home/user/wt-l2b/plugins/superheroes/lib/tests/test_ruling_window_c7.py:247: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_ruling_window_c7.py::test_a_ruling_on_a_row_in_the_emitted_order_leaves_the_attempt_untouched
1 failed in 1.59s
```

**Restore.** Inverse edit. Restored lines (`round_driver.py:7591-7593`):

```python
    if not emitted:
        _reconcile_fixer_queue_after_rulings(
            state, cfg, extra_rows=restored_rows, session_dir=session_dir)
```

Restore receipt: `sha256(round_driver.py)` first 16 hex digits `d82357d35b914254` before the neutralization and after the restore.

**Raw green** (exit 0):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 1.79s
```
