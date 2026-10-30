# Bite-proof record c1l9a_wo3_apply_fixes

The detectors this change adds: the check that a fix with a break-it test lands with its test
(`round_driver._apply_fixes_commit_fault`, `_fix_commit_test_fault`), and the move of a saved fixer step to
`apply-fixes` (`round_driver._migrate_fixer_step`, called from `_commit_recover_or_refuse`).

Guarded elements, declared up front by the order: G1 the binding is required, G2 the test is at the commit with the
block's bytes, G3 the commit changes something besides the test, G4 the commit is outside the step's start-head range,
G5 the generation-6 migration. One neutralization and one red each. Every neutralization was a targeted edit and was
undone only by the inverse edit; no `git checkout`, `git restore`, `git reset` or `git stash` was run.

Every run used: `scripts/pinned-python -B -X pycache_prefix=/home/user/superheroes/.git/pyc-wo3 -m pytest <one node> -q -p no:cacheprovider`
(`--timeout` is not an option of this pytest setup, so it was left out). No capture is redacted: none held a secret;
the temporary paths are pytest's own. Nothing was elided.

Status: G1, G2, G3, G4 are complete (red and green). **G5 is incomplete: its red was captured and its neutralization
was restored by the inverse edit, but its green run was refused and never ran** (see G5).

---

## G1 — a test-carrying finding with no binding is refused (`round_driver.py:5502`, axis: a binding is owed)

- neutralization: in `_apply_fixes_commit_fault`, `return "%s:%s:%s" % (FIX_WITHOUT_TEST, key, FIX_NO_BINDING), []` after `if not candidates:` became `continue`.
- detector: `test_apply_fixes_c1l9a.py::test_e2_a_test_carrying_finding_with_no_binding_refuses_and_the_step_stays_pending`
- raw red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_e2_a_test_carrying_finding_with_no_binding_refuses_and_the_step_stays_pending _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-17/test_e2_a_test_carrying_findin0')

    def test_e2_a_test_carrying_finding_with_no_binding_refuses_and_the_step_stays_pending(tmp_path):
        fx = Fixture(tmp_path)
        fx.reach()
        key = fx.keys()[0]
        fx.commit_fix()
>       fx.assert_refused_pending({"fixes": ["fixed it"]}, "%s:%s:no-binding" % (NO_TEST, key))

/home/user/wt-2213/plugins/superheroes/lib/tests/test_apply_fixes_c1l9a.py:271: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

self = <test_apply_fixes_c1l9a.Fixture object at 0x7f8077a6ae10>
artifact = {'fixes': ['fixed it']}
detail = 'fix-without-break-it-test:src/payments/charge.py::a retried charge is posted twice@L2:no-binding'

    def assert_refused_pending(self, artifact, detail):
        """The report refuses as `fold-refused` naming ``detail``, and the state file, the pending step and its
        attempt are exactly as they were."""
        before = TRD._state_bytes(str(self.session))
        out = self.submit(artifact)
>       assert out == {"ok": False, "reason": REFUSED, "detail": detail}, out
E       AssertionError: {'ok': True, 'round': 1, 'phase': 'apply-fixes', 'nextStep': 'dispatch-audits', ...}
E       assert {'ok': True, ...-audits', ...} == {'ok': False,...2:no-binding'}
E         
E         Differing items:
E         {'ok': True} != {'ok': False}
E         Left contains 4 more items:
E         {'foldLanded': True,
E          'nextStep': 'dispatch-audits',
E          'phase': 'apply-fixes',...
E         
E         ...Full output truncated, use '-vv' to show

/home/user/wt-2213/plugins/superheroes/lib/tests/test_apply_fixes_c1l9a.py:208: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_apply_fixes_c1l9a.py::test_e2_a_test_carrying_finding_with_no_binding_refuses_and_the_step_stays_pending
1 failed in 4.41s
```

- restore: the inverse edit, `continue` back to `return "%s:%s:%s" % (FIX_WITHOUT_TEST, key, FIX_NO_BINDING), []`.
- restore receipt (restored lines, quoted from the file after the edit):

```
5501-        # axis: a finding that carries a break-it test and is not left unfixed owes a binding — see bite-proof record c1l9a_wo3_apply_fixes
5502-        if not candidates:
5503:            return "%s:%s:%s" % (FIX_WITHOUT_TEST, key, FIX_NO_BINDING), []
```

- raw green:

```
.                                                                        [100%]
1 passed in 4.14s
```

## G2 — the test is at the block's path with the block's bytes exactly (`round_driver.py:5452`, axis: bytes)

- neutralization: in `_fix_commit_test_fault`, `if have != wanted:` became `if False:`.
- detector: `test_apply_fixes_c1l9a.py::test_e4_a_commit_whose_test_bytes_differ_from_the_block_refuses`
- raw red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_e4_a_commit_whose_test_bytes_differ_from_the_block_refuses ________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-19/test_e4_a_commit_whose_test_by0')

    def test_e4_a_commit_whose_test_bytes_differ_from_the_block_refuses(tmp_path):
        fx = Fixture(tmp_path)
        fx.reach()
        key = fx.keys()[0]
        sha = fx.commit_fix(test_content=_TEST_OTHER_BYTES)
>       fx.assert_refused_pending(_bound(key, sha), "%s:%s:test-bytes-differ" % (NO_TEST, key))

/home/user/wt-2213/plugins/superheroes/lib/tests/test_apply_fixes_c1l9a.py:290: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

self = <test_apply_fixes_c1l9a.Fixture object at 0x7f7f57fb20f0>
artifact = {'fixes': [{'finding': 'src/payments/charge.py::a retried charge is posted twice@L2', 'commit': 'a49c01cdc6685712df700b8dabeb531e8e83581b'}]}
detail = 'fix-without-break-it-test:src/payments/charge.py::a retried charge is posted twice@L2:test-bytes-differ'

    def assert_refused_pending(self, artifact, detail):
        """The report refuses as `fold-refused` naming ``detail``, and the state file, the pending step and its
        attempt are exactly as they were."""
        before = TRD._state_bytes(str(self.session))
        out = self.submit(artifact)
>       assert out == {"ok": False, "reason": REFUSED, "detail": detail}, out
E       AssertionError: {'ok': True, 'round': 1, 'phase': 'apply-fixes', 'nextStep': 'dispatch-audits', ...}
E       assert {'ok': True, ...-audits', ...} == {'ok': False,...bytes-differ'}
E         
E         Differing items:
E         {'ok': True} != {'ok': False}
E         Left contains 4 more items:
E         {'foldLanded': True,
E          'nextStep': 'dispatch-audits',
E          'phase': 'apply-fixes',...
E         
E         ...Full output truncated, use '-vv' to show

/home/user/wt-2213/plugins/superheroes/lib/tests/test_apply_fixes_c1l9a.py:208: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_apply_fixes_c1l9a.py::test_e4_a_commit_whose_test_bytes_differ_from_the_block_refuses
1 failed in 5.02s
```

- restore: the inverse edit, `if False:` back to `if have != wanted:`.
- restore receipt:

```
5451-    # axis: the test is at the block's path with the block's bytes exactly — see bite-proof record c1l9a_wo3_apply_fixes
5452:    if have != wanted:
5453-        return FIX_TEST_BYTES_DIFFER
```

- raw green:

```
.                                                                        [100%]
1 passed in 2.86s
```

## G3 — the commit changes at least one path besides the test (`round_driver.py:5455`, axis: a fix change)

- neutralization: in `_fix_commit_test_fault`, `if not any(p != path for p in changed):` became `if False:`.
- detector: `test_apply_fixes_c1l9a.py::test_e5_a_commit_that_changes_only_the_test_refuses`
- raw red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_e5_a_commit_that_changes_only_the_test_refuses ______________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-21/test_e5_a_commit_that_changes_0')

    def test_e5_a_commit_that_changes_only_the_test_refuses(tmp_path):
        fx = Fixture(tmp_path)
        fx.reach()
        key = fx.keys()[0]
        sha = fx.commit_fix(code=None)
>       fx.assert_refused_pending(_bound(key, sha), "%s:%s:no-fix-change" % (NO_TEST, key))

/home/user/wt-2213/plugins/superheroes/lib/tests/test_apply_fixes_c1l9a.py:298: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

self = <test_apply_fixes_c1l9a.Fixture object at 0x7f6ae0ddd160>
artifact = {'fixes': [{'finding': 'src/payments/charge.py::a retried charge is posted twice@L2', 'commit': '17d434db50f59e63fee44eb308045a7c4e73b50d'}]}
detail = 'fix-without-break-it-test:src/payments/charge.py::a retried charge is posted twice@L2:no-fix-change'

    def assert_refused_pending(self, artifact, detail):
        """The report refuses as `fold-refused` naming ``detail``, and the state file, the pending step and its
        attempt are exactly as they were."""
        before = TRD._state_bytes(str(self.session))
        out = self.submit(artifact)
>       assert out == {"ok": False, "reason": REFUSED, "detail": detail}, out
E       AssertionError: {'ok': True, 'round': 1, 'phase': 'apply-fixes', 'nextStep': 'dispatch-audits', ...}
E       assert {'ok': True, ...-audits', ...} == {'ok': False,...o-fix-change'}
E         
E         Differing items:
E         {'ok': True} != {'ok': False}
E         Left contains 4 more items:
E         {'foldLanded': True,
E          'nextStep': 'dispatch-audits',
E          'phase': 'apply-fixes',...
E         
E         ...Full output truncated, use '-vv' to show

/home/user/wt-2213/plugins/superheroes/lib/tests/test_apply_fixes_c1l9a.py:208: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_apply_fixes_c1l9a.py::test_e5_a_commit_that_changes_only_the_test_refuses
1 failed in 3.11s
```

- restore: the inverse edit, `if False:` back to `if not any(p != path for p in changed):`.
- restore receipt:

```
5454-    # axis: the commit changes something besides the test, so a test committed alone is no fix — see bite-proof record c1l9a_wo3_apply_fixes
5455:    if not any(p != path for p in changed):
5456-        return FIX_NO_FIX_CHANGE
```

- raw green:

```
.                                                                        [100%]
1 passed in 3.01s
```

## G4 — a commit reachable from the step's start head is refused (`round_driver.py:5438`, axis: start-head range)

- neutralization: in `_fix_commit_test_fault`, `if facts.get("inStep") is not False:` became `if False:`.
- detector: `test_apply_fixes_c1l9a.py::test_e6_a_commit_reachable_from_the_start_head_refuses_commit_not_in_step`
- raw red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
__ test_e6_a_commit_reachable_from_the_start_head_refuses_commit_not_in_step ___

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-23/test_e6_a_commit_reachable_fro0')

    def test_e6_a_commit_reachable_from_the_start_head_refuses_commit_not_in_step(tmp_path):
        fx = Fixture(tmp_path)
        n = fx.reach()
        key = fx.keys()[0]
        fx.commit_fix()
>       fx.assert_refused_pending(_bound(key, n["payload"]["startHead"]),
                                  "%s:%s:commit-not-in-step" % (NO_TEST, key))

/home/user/wt-2213/plugins/superheroes/lib/tests/test_apply_fixes_c1l9a.py:317: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

self = <test_apply_fixes_c1l9a.Fixture object at 0x7f4f0b69c5c0>
artifact = {'fixes': [{'finding': 'src/payments/charge.py::a retried charge is posted twice@L2', 'commit': 'cbefc32064df0ea6f25e9f3b6d3feba88ebb079a'}]}
detail = 'fix-without-break-it-test:src/payments/charge.py::a retried charge is posted twice@L2:commit-not-in-step'

    def assert_refused_pending(self, artifact, detail):
        """The report refuses as `fold-refused` naming ``detail``, and the state file, the pending step and its
        attempt are exactly as they were."""
        before = TRD._state_bytes(str(self.session))
        out = self.submit(artifact)
>       assert out == {"ok": False, "reason": REFUSED, "detail": detail}, out
E       AssertionError: {'ok': False, 'reason': 'fold-refused', 'detail': 'fix-without-break-it-test:src/payments/charge.py::a retried charge is posted twice@L2:test-missing'}
E       assert {'ok': False,...test-missing'} == {'ok': False,...-not-in-step'}
E         
E         Omitting 2 identical items, use -vv to show
E         Differing items:
E         {'detail': 'fix-without-break-it-test:src/payments/charge.py::a retried charge is posted twice@L2:test-missing'} != {'detail': 'fix-without-break-it-test:src/payments/charge.py::a retried charge is posted twice@L2:commit-not-in-step'}
E         Use -v to get more diff

/home/user/wt-2213/plugins/superheroes/lib/tests/test_apply_fixes_c1l9a.py:208: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_apply_fixes_c1l9a.py::test_e6_a_commit_reachable_from_the_start_head_refuses_commit_not_in_step
1 failed in 3.23s
```

- cases this detector does not discriminate: the start head's own commit carries no break-it test, so with the check neutralized the report is still refused, with `test-missing` instead of `commit-not-in-step`. The test goes red on the named reason, not on accept-versus-refuse; it does not show a fix-carrying, test-carrying commit already reachable from the start head being accepted. A commit that carries both the fix and the test and sits at or below the start head is the case that would show it.
- restore: the inverse edit, `if False:` back to `if facts.get("inStep") is not False:`.
- restore receipt:

```
5438:    if facts.get("inStep") is not False:
5439-        return FIX_COMMIT_NOT_IN_STEP
```

- raw green:

```
.                                                                        [100%]
1 passed in 2.86s
```

## G5 — a generation-6 session at the fixer step is migrated, not handed back (`round_driver._commit_recover_or_refuse`, axis: the migration runs before the retired-gate hand-back)

- neutralization: in `_commit_recover_or_refuse`, the call `_migrate_saved_fixer_step(session_dir, cmd)` was replaced by `pass`, ahead of `_hand_back_retired_gate(session_dir, cmd)`.
- detector: `test_fix_step_migration_c1l9a.py::test_e12_a_generation_6_session_at_the_fixer_step_is_migrated_not_handed_back`
- raw red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_e12_a_generation_6_session_at_the_fixer_step_is_migrated_not_handed_back _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-25/test_e12_a_generation_6_sessio0')

    def test_e12_a_generation_6_session_at_the_fixer_step_is_migrated_not_handed_back(tmp_path):
        # axis: the migration runs before the retired-gate hand-back, so a generation-6 fixer step is moved on — see bite-proof record c1l9a_wo3_apply_fixes
        session_dir, before, anchor = _migrated_session(tmp_path)
        assert before["sessionGeneration"] == 6
        out = RD.cmd_next(session_dir)
>       assert out["ok"] is True and out["action"] == out["phase"] == RD.P_APPLY_FIXES, out
E       AssertionError: {'ok': True, 'action': 'terminal', 'round': 7, 'phase': 'terminal', ...}
E       assert (True is True and 'terminal' == 'apply-fixes'
E         
E         - apply-fixes
E         + terminal)

/home/user/wt-2213/plugins/superheroes/lib/tests/test_fix_step_migration_c1l9a.py:70: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_fix_step_migration_c1l9a.py::test_e12_a_generation_6_session_at_the_fixer_step_is_migrated_not_handed_back
1 failed in 1.49s
```

- restore: the inverse edit, `pass` back to `_migrate_saved_fixer_step(session_dir, cmd)`. The edit reported success.
- restore receipt (the restored lines, as the inverse edit wrote them; the grep that was to quote them from the file was refused, see below):

```
    _migrate_saved_fixer_step(session_dir, cmd)
    _hand_back_retired_gate(session_dir, cmd)
    return None
```

- raw green: **not produced.** The command that was to quote the restored lines from the file and run this node (`grep -n -B1 -A2 '_migrate_saved_fixer_step(session_dir, cmd)$' plugins/superheroes/lib/round_driver.py; scripts/pinned-python … -m pytest "plugins/superheroes/lib/tests/test_fix_step_migration_c1l9a.py::test_e12_a_generation_6_session_at_the_fixer_step_is_migrated_not_handed_back" -q -p no:cacheprovider 2>&1`) was held by the harness: "This Bash command contains multiple operations. The following part requires approval". Nobody answered it, so it did not run. It was not retried in another form. The outstanding receipt is the orchestrator's: run that one node with the restored `round_driver.py` and expect `1 passed`. The one earlier run of all three new files together (32 passed) was made before any neutralization.
