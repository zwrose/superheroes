# Bite-proof record: WO1b (C7 L2b, issue #1868) — the ruling window

Detectors: `plugins/superheroes/lib/tests/test_ruling_window_c7.py` (unedited for every proof below).
Neutralized file: `plugins/superheroes/lib/round_driver.py`, each time by one targeted edit through the
edit tool, restored by the inverse edit. Every run: `python3 -B -X pycache_prefix=/tmp/claude-0/pyc -m
pytest '<exact node id>' -q -n 0`. Pytest-internal paths (`/tmp/claude-0/pytest-of-root/...`) are session
scratch, not secrets; nothing else is redacted.

Declared guarded elements (six): 1 withdraw restore check (dirty tree); 2 withdraw restore check (HEAD
moved); 3 `cmd_submit` fold-path refusal of a withdrawn attempt; 4 `_next_dispatch_attempt` floor;
5 conditional `ruling-attempt-pending`; 6 real-consequence lift.

Capture disclosures: the element 1 red is the last 40 lines of the run (the head of the failure listing is
cut). All other captures are whole. Elements 1 and 2 were re-run (new captures, new line numbers) after
the restore check began resolving the repo root through `store_core.repo_root` instead of a
`rev-parse --show-toplevel` call; elements 3-6 are unchanged from the earlier run.

## 1. Withdraw restore check, dirty tree

- Guarded element and axis: `_withdraw_restore_check`, `round_driver.py:7509` (`if dirty:`). Axis: a
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
- Restore: inverse edit `    if False and dirty:` -> `    if dirty:`. Restore receipt (lines 7509-7510 re-read):
  `    if dirty:` / `        return (WITHDRAW_WORKTREE_DIRTY,`.
- Raw green:

```
.                                                                        [100%]
1 passed in 6.07s
```

## 2. Withdraw restore check, HEAD moved

- Guarded element and axis: `_withdraw_restore_check`, `round_driver.py:7514` (`if head != bound:`). Axis:
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
- Restore: inverse edit. Restore receipt (lines 7514-7515 re-read): `    if head != bound:` /
  `        return (WITHDRAW_HEAD_MOVED,`.
- Raw green:

```
.                                                                        [100%]
1 passed in 2.37s
```

## 3. Fold-path refusal of a withdrawn attempt in `cmd_submit`

- Guarded element and axis: `cmd_submit`, `round_driver.py:7908-7909` (the `_fixer_attempt_withdrawn_refusal`
  call with `"submit"`). Axis: a submit addressed to a withdrawn fixer attempt is refused with
  `fixer-attempt-withdrawn`, naming the withdrawal.
- Detector: `test_edge3_fold_paths_refuse_a_withdrawn_attempt` (its first loop leg is the submit; the
  record-result and record-missing legs are other call sites and are not neutralized here).
- Neutralization: `        session_dir, "submit", state, attempt, phase=phase)` ->
  `        session_dir, "submit", state, None, phase=phase)` (the helper returns None for a non-int attempt;
  edit-tool uniqueness-checked; line 7909 re-read).
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
- Restore: inverse edit. Restore receipt (lines 7908-7909 re-read): `    withdrawn_refusal =
  _fixer_attempt_withdrawn_refusal(` / `        session_dir, "submit", state, attempt, phase=phase)`.
- Raw green:

```
.                                                                        [100%]
1 passed in 1.74s
```

## 4. `_next_dispatch_attempt` floor

- Guarded element and axis: `_next_dispatch_attempt`, `round_driver.py:8685`
  (`candidates.extend(_withdrawn_fixer_attempts(state, rnd))`). Axis: the attempt allocated after a
  withdrawal is strictly above the withdrawn one.
- Detector: `test_edge4_fresh_attempt_is_above_the_withdrawn_one`.
- Neutralization: `        candidates.extend(_withdrawn_fixer_attempts(state, rnd))` ->
  `        candidates.extend(())` (line 8685 re-read).
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
- Restore: inverse edit. Restore receipt (line 8685 re-read):
  `        candidates.extend(_withdrawn_fixer_attempts(state, rnd))`.
- Raw green:

```
.                                                                        [100%]
1 passed in 1.85s
```

## 5. Conditional `ruling-attempt-pending`

- Guarded element and axis: `_cmd_rule_locked`, `round_driver.py:7321`
  (`if _lineage_root(lineage, key) in batch_roots:`). Axis: a ruling that targets a finding in the emitted
  fixer batch is refused with `ruling-attempt-pending`.
- Detector: `test_t1_ruling_while_pending_reaches_the_fix`.
- Neutralization: `            if _lineage_root(lineage, key) in batch_roots:` ->
  `            if False and _lineage_root(lineage, key) in batch_roots:` (never refuses; line 7321 re-read).
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
- Restore: inverse edit. Restore receipt (line 7321 re-read):
  `            if _lineage_root(lineage, key) in batch_roots:`.
- Raw green:

```
.                                                                        [100%]
1 passed in 1.71s
```

## 6. Real-consequence lift

- Guarded element and axis: `_lift_marker_for`, `round_driver.py:4227` (the `LIFT_REAL_CONSEQUENCE`
  condition). Axis: an undisposed real-consequence Minor rides the first fixer order after the blocker.
- Detector: `test_t5_undisposed_real_minors_ride_the_first_fixer_order`.
- Neutralization: `    if (finding.get(review_findings_schema.CONSEQUENCE_KIND_KEY) == review_findings_schema.REAL`
  -> `    if (False and finding.get(review_findings_schema.CONSEQUENCE_KIND_KEY) == review_findings_schema.REAL`
  (real-consequence branch only; the guidance branch is untouched; line 4227 re-read).
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
- Restore: inverse edit. Restore receipt (line 4227 re-read):
  `    if (finding.get(review_findings_schema.CONSEQUENCE_KIND_KEY) == review_findings_schema.REAL`.
- Raw green:

```
.                                                                        [100%]
1 passed in 1.67s
```

## Final restore receipt

After the last restore, `git diff -- plugins/superheroes/lib/round_driver.py` shows only the
repo-root-resolver fix in `_withdraw_restore_check` (the `rev-parse --show-toplevel` call replaced by
`store_core.repo_root(root)`, with `RepoRootUnavailable` returned as `withdraw-git-unavailable`); no
neutralization remains.
