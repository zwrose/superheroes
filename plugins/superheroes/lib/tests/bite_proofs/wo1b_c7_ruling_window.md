# Bite-proof record: WO1b (C7 L2b, issue #1868) — the ruling window

Detectors: `plugins/superheroes/lib/tests/test_ruling_window_c7.py` (unedited for every proof below).
Neutralized file: `plugins/superheroes/lib/round_driver.py`, each time by one targeted edit through the
edit tool, restored by the inverse edit. Every run: `python3 -B -X pycache_prefix=/tmp/claude-0/pyc -m
pytest '<exact node id>' -q -n 0`. Pytest-internal paths (`/tmp/claude-0/pytest-of-root/...`) are session
scratch, not secrets; nothing else is redacted.

Declared guarded elements (eleven): 1 withdraw restore check (dirty tree); 2 withdraw restore check (HEAD
moved); 3 `cmd_submit` fold-path refusal of a withdrawn attempt; 4 `_next_dispatch_attempt` floor;
5 conditional `ruling-attempt-pending`; 6 real-consequence lift; 7 product-choice exclusion in the
real-consequence lift; 8 owner-judgment gate holds only blocking findings (`_after_findings_settled`
entry; the `_settle_delta` entry is listed unproven); 9 owner-named lift when no offered row survives;
10 autonomous lifts alone never start a leg (reconciled batch); 11 autonomous lifts never start a leg on
an empty offered set.

Capture disclosures: the element 1 red is the last 40 lines of the run (the head of the failure listing is
cut). All other captures are whole. Elements 1 and 2 were re-run (new captures, new line numbers) after
the restore check began resolving the repo root through `store_core.repo_root` instead of a
`rev-parse --show-toplevel` call; elements 3-6 are unchanged from the earlier run. Elements 7-11 were
added when below-blocking product choices stopped entering the owner gate; their runs are the new
captures below. The `round_driver.py:<line>` pointers of elements 1-6 were refreshed to the file as it
stands after that change (the neutralized text is unchanged, the earlier captures are not re-run).

## 1. Withdraw restore check, dirty tree

- Guarded element and axis: `_withdraw_restore_check`, `round_driver.py:7834` (`if dirty:`). Axis: a
  worktree still holding the stopped fixer's changes is refused with `withdraw-worktree-dirty`.
- Detector: `test_edge2_restore_check_refusals[tracked-change-withdraw-worktree-dirty]`.
- Neutralization: `    if dirty:` -> `    if False and dirty:` (asserted once by the edit tool; re-run after the
  fix that resolves the repo root through `store_core.repo_root`).
- Raw red (last 40 lines of the run):

```
keep_severity = None, case = 'tracked-change', token = 'withdraw-worktree-dirty'

    @pytest.mark.parametrize("case,token", [
        ("tracked-change", "withdraw-worktree-dirty"),
        ("untracked-file", "withdraw-worktree-dirty"),
        ("head-moved", "withdraw-head-moved"),
        ("no-anchor-head", "withdraw-head-unanchored"),
        ("git-unavailable", "withdraw-git-unavailable"),
    ])
    def test_edge2_restore_check_refusals(tmp_path, keep_severity, case, token):
        """axis: the worktree must be back at the attempt's starting head with nothing left over.
    
        bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo1b_c7_ruling_window.md (elements 1, 2)
        """
        session_dir, _g, _h, _f, _g2 = _two_important(tmp_path, "c7-e2")
        k = _state(session_dir)["pending"]["attempt"]
        repo, head = _throwaway_repo(tmp_path)
        _bind_anchor_head(session_dir, None if case == "no-anchor-head" else head)
        kwargs = {"repo_root": str(repo)}
        if case == "tracked-change":
            (repo / "a.txt").write_text("changed by the stopped fixer\n", encoding="utf-8")
        elif case == "untracked-file":
            (repo / "stray.txt").write_text("left behind\n", encoding="utf-8")
        elif case == "head-moved":
            (repo / "a.txt").write_text("two\n", encoding="utf-8")
            _git(repo, "commit", "-q", "-a", "-m", "second")
        elif case == "git-unavailable":
            kwargs = {"repo_root": str(repo), "git": lambda cwd, *args: None}
        before = _state_bytes(session_dir)
        out = RD.cmd_withdraw(session_dir, k, "owner ruled", **kwargs)
>       assert out.get("ok") is False and out.get("reason") == token, out
E       AssertionError: {'ok': True, 'withdrawn': {'round': 1, 'attempt': 0}, 'restoreCheck': 'checked'}
E       assert (True is False)
E        +  where True = <built-in method get of dict object at 0x7fd69fdacf40>('ok')
E        +    where <built-in method get of dict object at 0x7fd69fdacf40> = {'ok': True, 'withdrawn': {'round': 1, 'attempt': 0}, 'restoreCheck': 'checked'}.get

/home/user/wt-1868/plugins/superheroes/lib/tests/test_ruling_window_c7.py:466: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_ruling_window_c7.py::test_edge2_restore_check_refusals[tracked-change-withdraw-worktree-dirty]
1 failed in 6.95s
```

- Axis check: the withdraw went through (`ok: True`, `restoreCheck: checked`) where the refusal token
  `withdraw-worktree-dirty` was expected — red on the refusal axis.
- Restore: inverse edit `    if False and dirty:` -> `    if dirty:`. Restore receipt (lines 7834-7835 re-read):
  `    if dirty:` / `        return (WITHDRAW_WORKTREE_DIRTY,`.
- Raw green:

```
.                                                                        [100%]
1 passed in 6.07s
```

## 2. Withdraw restore check, HEAD moved

- Guarded element and axis: `_withdraw_restore_check`, `round_driver.py:7839` (`if head != bound:`). Axis:
  a worktree at a different head than the attempt started from is refused with `withdraw-head-moved`.
- Detector: `test_edge2_restore_check_refusals[head-moved-withdraw-head-moved]`.
- Neutralization: `    if head != bound:` -> `    if False and head != bound:` (asserted once by the edit
  tool; re-run after the same fix).
- Raw red (whole run):

```
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_edge2_restore_check_refusals[head-moved-withdraw-head-moved] _______

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-74/test_edge2_restore_check_refus0')
keep_severity = None, case = 'head-moved', token = 'withdraw-head-moved'

    @pytest.mark.parametrize("case,token", [
        ("tracked-change", "withdraw-worktree-dirty"),
        ("untracked-file", "withdraw-worktree-dirty"),
        ("head-moved", "withdraw-head-moved"),
        ("no-anchor-head", "withdraw-head-unanchored"),
        ("git-unavailable", "withdraw-git-unavailable"),
    ])
    def test_edge2_restore_check_refusals(tmp_path, keep_severity, case, token):
        """axis: the worktree must be back at the attempt's starting head with nothing left over.
    
        bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo1b_c7_ruling_window.md (elements 1, 2)
        """
        session_dir, _g, _h, _f, _g2 = _two_important(tmp_path, "c7-e2")
        k = _state(session_dir)["pending"]["attempt"]
        repo, head = _throwaway_repo(tmp_path)
        _bind_anchor_head(session_dir, None if case == "no-anchor-head" else head)
        kwargs = {"repo_root": str(repo)}
        if case == "tracked-change":
            (repo / "a.txt").write_text("changed by the stopped fixer\n", encoding="utf-8")
        elif case == "untracked-file":
            (repo / "stray.txt").write_text("left behind\n", encoding="utf-8")
        elif case == "head-moved":
            (repo / "a.txt").write_text("two\n", encoding="utf-8")
            _git(repo, "commit", "-q", "-a", "-m", "second")
        elif case == "git-unavailable":
            kwargs = {"repo_root": str(repo), "git": lambda cwd, *args: None}
        before = _state_bytes(session_dir)
        out = RD.cmd_withdraw(session_dir, k, "owner ruled", **kwargs)
>       assert out.get("ok") is False and out.get("reason") == token, out
E       AssertionError: {'ok': True, 'withdrawn': {'round': 1, 'attempt': 0}, 'restoreCheck': 'checked'}
E       assert (True is False)
E        +  where True = <built-in method get of dict object at 0x7fdc16ee1d40>('ok')
E        +    where <built-in method get of dict object at 0x7fdc16ee1d40> = {'ok': True, 'withdrawn': {'round': 1, 'attempt': 0}, 'restoreCheck': 'checked'}.get

/home/user/wt-1868/plugins/superheroes/lib/tests/test_ruling_window_c7.py:466: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_ruling_window_c7.py::test_edge2_restore_check_refusals[head-moved-withdraw-head-moved]
1 failed in 3.59s
```

- Axis check: same as element 1 for the head token; the fixture commits (clean tree, moved head), so the
  dirty check does not fire first.
- Restore: inverse edit. Restore receipt (lines 7839-7840 re-read): `    if head != bound:` /
  `        return (WITHDRAW_HEAD_MOVED,`.
- Raw green:

```
.                                                                        [100%]
1 passed in 2.37s
```

## 3. Fold-path refusal of a withdrawn attempt in `cmd_submit`

- Guarded element and axis: `cmd_submit`, `round_driver.py:8238-8239` (the `_fixer_attempt_withdrawn_refusal`
  call with `"submit"`). Axis: a submit addressed to a withdrawn fixer attempt is refused with
  `fixer-attempt-withdrawn`, naming the withdrawal.
- Detector: `test_edge3_fold_paths_refuse_a_withdrawn_attempt` (its first loop leg is the submit; the
  record-result and record-missing legs are other call sites and are not neutralized here).
- Neutralization: `        session_dir, "submit", state, attempt, phase=phase)` ->
  `        session_dir, "submit", state, None, phase=phase)` (the helper returns None for a non-int attempt;
  edit-tool uniqueness-checked; line 8239 re-read).
- Raw red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_______________ test_edge3_fold_paths_refuse_a_withdrawn_attempt _______________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-34/test_edge3_fold_paths_refuse_a0')
keep_severity = None

    def test_edge3_fold_paths_refuse_a_withdrawn_attempt(tmp_path, keep_severity):
        """axis: submit, record-result and record-missing addressed to a withdrawn fixer attempt name the
        withdrawal, and leave the state alone."""
        session_dir, _g, _h, _f, _g2 = _two_important(tmp_path, "c7-e3")
        state = _state(session_dir)
        k = state["pending"]["attempt"]
        roster, _ = round_adapters.roster_for(P_FIXER, state, state.get("config") or {})
        seat = RR.roster_slots(roster)[0][0]
        assert RD.cmd_withdraw(session_dir, k, "owner ruled")["ok"]
        before = _state_bytes(session_dir)
        for out in (RD.cmd_submit(session_dir, P_FIXER, k, "h", {"fixes": []}),
                    RD.cmd_record_result(session_dir, seat, attempt=k),
                    RD.cmd_record_missing(session_dir, seat, k, "no-output")):
>           assert out.get("ok") is False and out.get("reason") == "fixer-attempt-withdrawn", out
E           AssertionError: {'ok': False, 'reason': 'advance-submit-interleaved'}
E           assert (False is False and 'advance-submit-interleaved' == 'fixer-attempt-withdrawn'
E            +  where False = <built-in method get of dict object at 0x7f781aff1d00>('ok')
E            +    where <built-in method get of dict object at 0x7f781aff1d00> = {'ok': False, 'reason': 'advance-submit-interleaved'}.get
E             
E             - fixer-attempt-withdrawn
E             + advance-submit-interleaved)

/home/user/wt-1868/plugins/superheroes/lib/tests/test_ruling_window_c7.py:515: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_ruling_window_c7.py::test_edge3_fold_paths_refuse_a_withdrawn_attempt
1 failed in 1.68s
```

- Axis check: the submit is still refused, but by a different downstream check
  (`advance-submit-interleaved`); the detector bites on the refusal token, which is the axis (a wrong token
  counts as red).
- Restore: inverse edit. Restore receipt (lines 8238-8239 re-read): `    withdrawn_refusal =
  _fixer_attempt_withdrawn_refusal(` / `        session_dir, "submit", state, attempt, phase=phase)`.
- Raw green:

```
.                                                                        [100%]
1 passed in 1.74s
```

## 4. `_next_dispatch_attempt` floor

- Guarded element and axis: `_next_dispatch_attempt`, `round_driver.py:9015`
  (`candidates.extend(_withdrawn_fixer_attempts(state, rnd))`). Axis: the attempt allocated after a
  withdrawal is strictly above the withdrawn one.
- Detector: `test_edge4_fresh_attempt_is_above_the_withdrawn_one`.
- Neutralization: `        candidates.extend(_withdrawn_fixer_attempts(state, rnd))` ->
  `        candidates.extend(())` (line 9015 re-read).
- Raw red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_edge4_fresh_attempt_is_above_the_withdrawn_one ______________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-36/test_edge4_fresh_attempt_is_ab0')
keep_severity = None

    def test_edge4_fresh_attempt_is_above_the_withdrawn_one(tmp_path, keep_severity):
        """axis: the attempt allocated after a withdrawal is strictly greater, its orders are emitted at
        that attempt, and the withdrawn attempt's order files stay on disk untouched.
    
        bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo1b_c7_ruling_window.md (element 4)
        """
        session_dir, _g, _h, _f, _g2 = _two_important(tmp_path, "c7-e4")
        state = _state(session_dir)
        k = state["pending"]["attempt"]
        old_order = _order_path(session_dir, state)
        manifest = RD._orders_manifest_path(session_dir, state["round"], P_FIXER, k)
        with open(old_order, "rb") as fh:
            old_order_bytes = fh.read()
        with open(manifest, "rb") as fh:
            old_manifest_bytes = fh.read()
        assert RD.cmd_withdraw(session_dir, k, "owner ruled")["ok"]
>       assert RD._next_dispatch_attempt(session_dir, state["round"], P_FIXER, _state(session_dir)) > k
E       AssertionError: assert 0 > 0
E        +  where 0 = <function _next_dispatch_attempt at 0x7f369682af20>('/tmp/claude-0/pytest-of-root/pytest-36/test_edge4_fresh_attempt_is_ab0/c7-e4', 1, 'dispatch-fixer', {'_advanceUsed': True, '_changedSubjectsSincePanel': [], '_coverage': [], '_fixBatch': [{'classification': 'mechanical...eviewer-found defect stays in the change', 'consequenceKind': 'real', 'detail': 'bounds F at src/f00.py:1', ...}], ...})
E        +    where <function _next_dispatch_attempt at 0x7f369682af20> = RD._next_dispatch_attempt
E        +    and   {'_advanceUsed': True, '_changedSubjectsSincePanel': [], '_coverage': [], '_fixBatch': [{'classification': 'mechanical...eviewer-found defect stays in the change', 'consequenceKind': 'real', 'detail': 'bounds F at src/f00.py:1', ...}], ...} = _state('/tmp/claude-0/pytest-of-root/pytest-36/test_edge4_fresh_attempt_is_ab0/c7-e4')

/home/user/wt-1868/plugins/superheroes/lib/tests/test_ruling_window_c7.py:536: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_ruling_window_c7.py::test_edge4_fresh_attempt_is_above_the_withdrawn_one
1 failed in 1.65s
```

- Axis check: the allocator returned 0, the withdrawn attempt's own number, where > 0 was required.
- Restore: inverse edit. Restore receipt (line 9015 re-read):
  `        candidates.extend(_withdrawn_fixer_attempts(state, rnd))`.
- Raw green:

```
.                                                                        [100%]
1 passed in 1.85s
```

## 5. Conditional `ruling-attempt-pending`

- Guarded element and axis: `_cmd_rule_locked`, `round_driver.py:7627`
  (`if _lineage_root(lineage, key) in batch_roots:`). Axis: a ruling that targets a finding in the emitted
  fixer batch is refused with `ruling-attempt-pending`.
- Detector: `test_t1_ruling_while_pending_reaches_the_fix`.
- Neutralization: `            if _lineage_root(lineage, key) in batch_roots:` ->
  `            if False and _lineage_root(lineage, key) in batch_roots:` (never refuses; line 7627 re-read).
- Raw red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________________ test_t1_ruling_while_pending_reaches_the_fix _________________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-38/test_t1_ruling_while_pending_r0')
keep_severity = None

    def test_t1_ruling_while_pending_reaches_the_fix(tmp_path, keep_severity):
        """axis: a ruling given while a fixer attempt is pending is refused with the recovery, and after
        `withdraw` it reaches the fix that follows; the withdrawn attempt can never fold.
    
        bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo1b_c7_ruling_window.md (elements 3, 5)
        """
        session_dir, _gitdir, _head, key_f, _key_g = _two_important(tmp_path)
        k = _state(session_dir)["pending"]["attempt"]
        ruling = _guidance_file(tmp_path, "r.json", key_f, "wrap it in the retry guard")
        before = _state_bytes(session_dir)
        out = _rule(session_dir, ruling)
>       assert out.get("ok") is False and out.get("reason") == "ruling-attempt-pending", out
E       AssertionError: {'ok': True, 'recorded': 1, 'rulingFileSha256': '17ee93be3925322d489590729b529fe2f6a5ca291535d5711cc7cd328ed5981d', 'action': 'dispatch-fixer', ...}
E       assert (True is False)
E        +  where True = <built-in method get of dict object at 0x7f4df0eeef80>('ok')
E        +    where <built-in method get of dict object at 0x7f4df0eeef80> = {'ok': True, 'recorded': 1, 'rulingFileSha256': '17ee93be3925322d489590729b529fe2f6a5ca291535d5711cc7cd328ed5981d', 'action': 'dispatch-fixer', ...}.get

/home/user/wt-1868/plugins/superheroes/lib/tests/test_ruling_window_c7.py:189: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_ruling_window_c7.py::test_t1_ruling_while_pending_reaches_the_fix
1 failed in 1.77s
```

- Axis check: the rule was accepted (`ok: True`) where the refusal token was required.
- Restore: inverse edit. Restore receipt (line 7627 re-read):
  `            if _lineage_root(lineage, key) in batch_roots:`.
- Raw green:

```
.                                                                        [100%]
1 passed in 1.71s
```

## 6. Real-consequence lift

- Guarded element and axis: `_lift_marker_for`, `round_driver.py:4439` (the `LIFT_REAL_CONSEQUENCE`
  condition). Axis: an undisposed real-consequence Minor rides the first fixer order after the blocker.
- Detector: `test_t5_undisposed_real_minors_ride_the_first_fixer_order`.
- Neutralization: `    if (finding.get(review_findings_schema.CONSEQUENCE_KIND_KEY) == review_findings_schema.REAL`
  -> `    if (False and finding.get(review_findings_schema.CONSEQUENCE_KIND_KEY) == review_findings_schema.REAL`
  (real-consequence branch only; the guidance branch is untouched; line 4439 re-read).
- Raw red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_t5_undisposed_real_minors_ride_the_first_fixer_order ___________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-40/test_t5_undisposed_real_minors0')
keep_severity = None

    def test_t5_undisposed_real_minors_ride_the_first_fixer_order(tmp_path, keep_severity):
        """axis: a round that sends a fixer out offers its undisposed real-consequence Minors in that same
        batch, after the blocker, each marked; a code-quality Minor is not lifted.
    
        bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo1b_c7_ruling_window.md (element 6)
        """
        session_dir, _g, _h = _minors_session(tmp_path, "c7-lift")
        state = _state(session_dir)
        assert state["pending"]["phase"] == P_FIXER
        by_title = _rows_by_title(state)
>       assert [row["title"] for row in state["_fixBatch"]] == [
            "blocker B", "real minor one", "real minor two"]
E       AssertionError: assert ['blocker B'] == ['blocker B',...al minor two']
E         
E         Right contains 2 more items, first extra item: 'real minor one'
E         Use -v to get more diff

/home/user/wt-1868/plugins/superheroes/lib/tests/test_ruling_window_c7.py:323: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_ruling_window_c7.py::test_t5_undisposed_real_minors_ride_the_first_fixer_order
1 failed in 1.68s
```

- Axis check: the batch holds only the blocker; the two real-consequence Minors are missing from it.
- Restore: inverse edit. Restore receipt (line 4439 re-read):
  `    if (finding.get(review_findings_schema.CONSEQUENCE_KIND_KEY) == review_findings_schema.REAL`.
- Raw green:

```
.                                                                        [100%]
1 passed in 1.67s
```

## 7. Product-choice exclusion in the real-consequence lift

Runs 7-11 use the pinned runner: `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc-wo
-m pytest '<exact node id>' -q -n 0 -p no:cacheprovider` from the worktree root. Pytest-internal paths
(`/private/tmp/claude-501/pytest-of-zwrose/...`) are session scratch; nothing is redacted. Before the
first neutralization `round_driver.py` was copied to session scratch; each restore was checked with
`cmp` against that copy (`IDENTICAL`).

- Guarded element and axis: `_lift_marker_for`, `round_driver.py:4440` (`and not finding.get("tradeoff")`
  in the real-consequence branch). Axis: an undecided real-consequence Minor product choice
  (`tradeoff: true`) never rides a fix batch autonomously.
- Detector: `test_an_undecided_product_choice_is_not_lifted_beside_a_blocker`.
- Neutralization: `            and not finding.get("tradeoff")` -> `            and True`.
- Raw red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_an_undecided_product_choice_is_not_lifted_beside_a_blocker ________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1653/test_an_undecided_product_choi0')
keep_severity = None

    def test_an_undecided_product_choice_is_not_lifted_beside_a_blocker(tmp_path, keep_severity):
        """axis: I1 — an undecided real-consequence Minor product choice never rides the blocker's batch."""
        session_dir, _g, _h = _session(
            tmp_path, [_finding("blocker B", 1), _choice("minor choice", 2)], name="c7-choice")
        state = _state(session_dir)
>       assert [row["title"] for row in state["_fixBatch"]] == ["blocker B"]
E       AssertionError: assert ['blocker B', 'minor choice'] == ['blocker B']
E         
E         Left contains one more item: 'minor choice'
E         Use -v to get more diff

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1868-e28e3164b3fd6e36/plugins/superheroes/lib/tests/test_ruling_window_c7.py:679: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_ruling_window_c7.py::test_an_undecided_product_choice_is_not_lifted_beside_a_blocker
1 failed in 5.78s
```

- Axis check: the batch holds the blocker and the undecided product choice; the choice was expected out.
- Restore: inverse edit `            and True` -> `            and not finding.get("tradeoff")`. Restore
  receipt: lines 4439-4441 re-read (`if (finding.get(review_findings_schema.CONSEQUENCE_KIND_KEY) ==
  review_findings_schema.REAL` / `and not finding.get("tradeoff")` / `and ruling != "out-of-scope" and
  disposition != "out-of-scope"`); `cmp` against the pre-neutralization copy: `IDENTICAL`.
- Raw green:

```
.                                                                        [100%]
1 passed in 5.65s
```

## 8. Owner-judgment gate holds only blocking findings

- Guarded element and axis: `_after_findings_settled`, `round_driver.py:4332`
  (`_route_judgment_blockers(state, blocking)`). Axis: the rows put to the owner gate are the blocking
  rows only; a below-blocking product choice never reaches `_judgmentFindings`. The same call shape at
  the `_settle_delta` gate entry (`round_driver.py:5766`) is listed as unproven: no detector this
  order adds drives a below-blocking tradeoff through the delta settle.
- Detector: `test_t_i_an_undecided_product_choice_is_left_for_the_owner[mechanical]`.
- Neutralization: `        if _route_judgment_blockers(state, blocking):` -> `        if
  _route_judgment_blockers(state, blocking + [f for f in (state.get("findings") or []) if
  f.get("tradeoff") and f not in blocking]):` (the live below-blocking product choice joins the rows
  offered to the gate).
- Raw red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_t_i_an_undecided_product_choice_is_left_for_the_owner[mechanical] ____

blocker_is_tradeoff = False

    @pytest.mark.parametrize("blocker_is_tradeoff", [False, True], ids=["mechanical", "gate-blocker"])
    def test_t_i_an_undecided_product_choice_is_left_for_the_owner(blocker_is_tradeoff):
        """axis: I1/I2 — an undecided below-blocking product choice never enters the owner gate or a fix
        batch, and the end-of-loop settle leaves it for the owner."""
        state = _unit_round([_unit_finding("B", 1, "Important", tradeoff=blocker_is_tradeoff),
                             _unit_finding("M", 2, "Minor", tradeoff=True)])
        if blocker_is_tradeoff:
            assert state["step"] == RD.P_JUDGMENT
            assert [r["findingKey"] for r in state["_judgmentFindings"]] == ["B"]
            assert state["_judgmentMechanical"] == []
            RD._fold_judgment(state, state["config"], {"dispositions": [
                {"id": _unit_gate_ids(state)[0], "disposition": "fix-as-suggested"}]})
>       assert state["step"] == P_FIXER
E       AssertionError: assert 'present-judgment' == 'dispatch-fixer'
E         
E         - dispatch-fixer
E         + present-judgment

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1868-e28e3164b3fd6e36/plugins/superheroes/lib/tests/test_ruling_window_c7.py:759: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_ruling_window_c7.py::test_t_i_an_undecided_product_choice_is_left_for_the_owner[mechanical]
1 failed in 0.62s
```

- Axis check: the round with a mechanical blocker and a below-blocking choice parked at the owner gate
  (`present-judgment`) instead of the fixer step.
- Restore: inverse edit back to `        if _route_judgment_blockers(state, blocking):`. Restore receipt:
  lines 4331-4333 re-read (`    if blocking:` / `        if _route_judgment_blockers(state, blocking):`
  / `            return`); `cmp` against the pre-neutralization copy: `IDENTICAL`.
- Raw green:

```
.                                                                        [100%]
1 passed in 0.19s
```

## 9. Owner-named lift when no offered row survives

- Guarded element and axis: `_queue_fix_batch`, `round_driver.py:4553`
  (`if lift and reset_accumulator and batch_index == 0:`, whose call passes `owner_named_only=not
  filtered`). Axis: with every offered row excluded or none offered (the gate's only blocker skipped),
  a finding an owner decision names still gets a fixer leg.
- Detector: `test_t_ii_c_a_guided_choice_survives_skipping_the_only_gate_blocker`.
- Neutralization: `    if lift and reset_accumulator and batch_index == 0:` -> `    if lift and
  reset_accumulator and batch_index == 0 and filtered:` (the lift only joins a non-empty batch).
- Raw red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_t_ii_c_a_guided_choice_survives_skipping_the_only_gate_blocker ______

    def test_t_ii_c_a_guided_choice_survives_skipping_the_only_gate_blocker():
        """axis: I1(b)/I3 — with the gate's only blocker skipped, a guided product choice still reaches
        the fixer through the chokepoint."""
        state = _unit_round([_unit_finding("J", 1, "Important", tradeoff=True),
                             _unit_finding("M", 2, "Minor", tradeoff=True)])
        assert [r["findingKey"] for r in state["_judgmentFindings"]] == ["J"]
        _unit_rulings(state, dict(findingKey="M", ruling="guidance", guidance="apply it"))
        RD._fold_judgment(state, state["config"], {"dispositions": [
            {"id": _unit_gate_ids(state)[0], "disposition": "skip", "reason": "keep current"}]})
>       assert state["step"] == P_FIXER
E       AssertionError: assert 'terminal' == 'dispatch-fixer'
E         
E         - dispatch-fixer
E         + terminal

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1868-e28e3164b3fd6e36/plugins/superheroes/lib/tests/test_ruling_window_c7.py:777: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_ruling_window_c7.py::test_t_ii_c_a_guided_choice_survives_skipping_the_only_gate_blocker
1 failed in 0.20s
```

- Axis check: the round settled at the terminal with the guided choice never sent to a fixer.
- Restore: inverse edit back to `    if lift and reset_accumulator and batch_index == 0:`. Restore receipt:
  lines 4553-4554 re-read (`    if lift and reset_accumulator and batch_index == 0:` / `        filtered =
  _lift_into_fix_batch(state, filtered, owner_named_only=not filtered)`); `cmp` against the
  pre-neutralization copy: `IDENTICAL`.
- Raw green:

```
.                                                                        [100%]
1 passed in 0.17s
```

## 10. Autonomous lifts alone never start a leg (reconciled batch)

- Guarded element and axis: `_queue_fix_batch`, `round_driver.py:4551`
  (`if batch_index == 0 and _holds_only_autonomous_lifts(state, filtered):`). Axis: a batch left holding
  only autonomous real-consequence lifts (their blocker ruled out) settles instead of dispatching a
  fixer.
- Detector: `test_an_autonomous_lifted_minor_alone_still_converges`.
- Neutralization: `    if batch_index == 0 and _holds_only_autonomous_lifts(state, filtered):` -> `    if
  False and batch_index == 0 and _holds_only_autonomous_lifts(state, filtered):`.
- Raw red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_an_autonomous_lifted_minor_alone_still_converges _____________

    def test_an_autonomous_lifted_minor_alone_still_converges():
        state, row = _lifted_minor_state()
>       assert RD._queue_fix_batch(state, state["config"], [row]) == "excluded"
E       AssertionError: assert 'queued' == 'excluded'
E         
E         - excluded
E         + queued

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1868-e28e3164b3fd6e36/plugins/superheroes/lib/tests/test_ruling_window_c7.py:1093: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_ruling_window_c7.py::test_an_autonomous_lifted_minor_alone_still_converges
1 failed in 0.18s
```

- Axis check: the lone autonomous lift was dispatched (`queued`) where the exclusion-emptied settle
  (`excluded`) was expected.
- Restore: inverse edit back to `    if batch_index == 0 and _holds_only_autonomous_lifts(state, filtered):`.
  Restore receipt: lines 4551-4552 re-read (that `if` / `        filtered = []`); `cmp` against the
  pre-neutralization copy: `IDENTICAL`.
- Raw green:

```
.                                                                        [100%]
1 passed in 0.17s
```

## 11. Autonomous lifts never start a leg on an empty offered set

- Guarded element and axis: `_lift_into_fix_batch`, `round_driver.py:4517` (`if owner_named_only:`).
  Axis: when no row is offered, only an owner-named finding is lifted; an undisposed real-consequence
  finding alone never makes a batch, and the call reports `empty` with nothing recorded.
- Detector: `test_edge7_a_round_with_no_offered_rows_lifts_nothing`.
- Neutralization: `    if owner_named_only:` -> `    if False and owner_named_only:`.
- Raw red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_edge7_a_round_with_no_offered_rows_lifts_nothing _____________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1661/test_edge7_a_round_with_no_off0')
keep_severity = None

    def test_edge7_a_round_with_no_offered_rows_lifts_nothing(tmp_path, keep_severity):
        """axis: an autonomous lift never starts a fixer leg. A Minor-only round converges with no fixer
        leg, and an empty offered set lifts nothing (and records no exclusion) though real-consequence
        findings are live."""
        minor_only = tmp_path / "minor-only"
        minor_only.mkdir()
        session_dir, gitdir, head_path = _bootstrap(minor_only, name="c7-e7")
        folded = _TRI._drive_to_terminal(
            session_dir, gitdir, [_finding("only minor", 1, "Minor", "real")], head_path)
        assert P_FIXER not in folded, folded
        final = _state(session_dir)
        assert final.get("terminal") == "converged"
        assert "liftedIntoFixBatch" not in final["rounds"]["1"]
    
        session_dir, _g, _h = _minors_session(tmp_path, "c7-e7-direct")
        state = _state(session_dir)
        assert any(f.get("consequenceKind") == "real" for f in state["findings"])
        state["pending"] = None
        state["rounds"]["1"].pop("liftedIntoFixBatch", None)
        before = (state.get("_fixBatch"), state.get("_fixQueue"), state.get("step"))
>       assert RD._queue_fix_batch(state, state["config"], []) == "empty"
E       AssertionError: assert 'queued' == 'empty'
E         
E         - empty
E         + queued

/Users/zwrose/.superheroes-worktrees/superheroes/issue-1868-e28e3164b3fd6e36/plugins/superheroes/lib/tests/test_ruling_window_c7.py:644: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_ruling_window_c7.py::test_edge7_a_round_with_no_offered_rows_lifts_nothing
1 failed in 10.56s
```

- Axis check: with nothing offered and no owner decision, the live real-consequence Minors made a batch
  (`queued`); the first (Minor-only converges) half of the test passed before this point.
- Restore: inverse edit back to `    if owner_named_only:`. Restore receipt: lines 4517-4519 re-read
  (`    if owner_named_only:` / `        effective = _live_ruling_by_key(state)` / `        lifted = [row for
  row in lifted if _owner_named_row(row, effective)]`); `cmp` against the pre-neutralization copy:
  `IDENTICAL`.
- Raw green:

```
.                                                                        [100%]
1 passed in 12.11s
```

## Final restore receipt

After the last restore, `git diff -- plugins/superheroes/lib/round_driver.py` shows only the
repo-root-resolver fix in `_withdraw_restore_check` (the `rev-parse --show-toplevel` call replaced by
`store_core.repo_root(root)`, with `RepoRootUnavailable` returned as `withdraw-git-unavailable`); no
neutralization remains.

Elements 7-11 were each restored by the inverse edit and checked against a pre-neutralization copy of
`round_driver.py` with `cmp` (`IDENTICAL` every time); the file's remaining diff against the branch head
is the order's own change (the lift no longer reaches the owner gate, the chokepoint lifts owner-named
rows), not a neutralization.
