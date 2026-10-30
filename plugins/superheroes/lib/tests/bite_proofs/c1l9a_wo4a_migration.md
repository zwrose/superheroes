# Bite-proof record c1l9a_wo4a_migration

The detectors this order adds: the start-head check's second detector
(`test_apply_fixes_c1l9a.py::test_e6_a_complete_commit_reachable_from_the_start_head_refuses_commit_not_in_step`), and
the absence test for the retired fixer phase (`test_no_fixer_phase_c1l9a.py`).

Guarded elements, declared up front by the order: G1 the start-head range check in
`round_driver._fix_commit_test_fault`; G2 the absence test's allowlist. One neutralization and one red each. Both
neutralizations were probes: a single targeted edit, undone only by the inverse edit; no `git checkout`, `git restore`,
`git reset` or `git stash` was run.

Every run used, from `/home/user/wt-2213-wo4a`:
`scripts/pinned-python -B -X pycache_prefix=/home/user/superheroes/.git/pyc-wo4a -m pytest <one node or file> -q -p no:cacheprovider -n auto`.
No capture is redacted: none held a secret; the temporary paths are pytest's own. The red captures are the last lines of
the run (the runner's own tail); nothing in the part shown was elided.

Both probes ran against this worktree alone: the two detectors need only files of this order and the production module
they guard.

---

## G1 — a commit that carries the fix and the test is still refused when it is reachable from the step's start head (`round_driver.py:5438`, axis: the start-head range)

The earlier E6 test binds the start head itself, a commit with no test in it, so with the range check neutralized it
still refuses, with `test-missing`. The new test binds a commit that carries both the charge fix and the test file and
moves the step's start head onto it, so only the range check can refuse it.

- neutralization: in `_fix_commit_test_fault`, `if facts.get("inStep") is not False:` became `if False:`.
- detector: `test_apply_fixes_c1l9a.py::test_e6_a_complete_commit_reachable_from_the_start_head_refuses_commit_not_in_step`
- raw red:

```
        fx.reach()
        key = fx.keys()[0]
        sha = fx.commit_fix()
        assert sorted(git(fx.repo, "show", "--name-only", "--format=", sha).split()) == [CHARGE_PATH, TEST_PATH]
        # the step began at a head that already holds the commit, which carries the fix and the test
        state = fx.state()
        state["_fixStepHead"] = sha
        RD.save_state(str(fx.session), state)
        fx.pending = RD.cmd_next(str(fx.session))
>       fx.assert_refused_pending(_bound(key, sha), "%s:%s:commit-not-in-step" % (NO_TEST, key))

/home/user/wt-2213-wo4a/plugins/superheroes/lib/tests/test_apply_fixes_c1l9a.py:334: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

self = <test_apply_fixes_c1l9a.Fixture object at 0x7f31d64bb500>
artifact = {'fixes': [{'finding': 'src/payments/charge.py::a retried charge is posted twice@L2', 'commit': 'f48336260006458b1f49a3d712043bc2cfcd3742'}]}
detail = 'fix-without-break-it-test:src/payments/charge.py::a retried charge is posted twice@L2:commit-not-in-step'

    def assert_refused_pending(self, artifact, detail):
        """The report refuses as `fold-refused` naming ``detail``, and the state file, the pending step and its
        attempt are exactly as they were."""
        before = TRD._state_bytes(str(self.session))
        out = self.submit(artifact)
>       assert out == {"ok": False, "reason": REFUSED, "detail": detail}, out
E       AssertionError: {'ok': True, 'round': 1, 'phase': 'apply-fixes', 'nextStep': 'dispatch-audits', ...}
E       assert {'ok': True, ...-audits', ...} == {'ok': False,...-not-in-step'}
E         
E         Differing items:
E         {'ok': True} != {'ok': False}
E         Left contains 4 more items:
E         {'foldLanded': True,
E          'nextStep': 'dispatch-audits',
E          'phase': 'apply-fixes',...
E         
E         ...Full output truncated, use '-vv' to show

/home/user/wt-2213-wo4a/plugins/superheroes/lib/tests/test_apply_fixes_c1l9a.py:209: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_apply_fixes_c1l9a.py::test_e6_a_complete_commit_reachable_from_the_start_head_refuses_commit_not_in_step
1 failed in 11.56s
```

With the check neutralized the fold succeeded (`'ok': True`, next step `dispatch-audits`), so the detector bites.

- restore: the inverse edit, `if False:` back to `if facts.get("inStep") is not False:`.
- restore receipt: `git diff --stat -- plugins/superheroes/lib/round_driver.py` printed nothing after the restore, and
  `sed -n 5436,5440p` printed:

```
    if not isinstance(facts, dict) or facts.get("reachable") is not True:
        return FIX_COMMIT_UNKNOWN
    if facts.get("inStep") is not False:
        return FIX_COMMIT_NOT_IN_STEP
    path = block["path"]
```

- raw green:

```
bringing up nodes...
bringing up nodes...

.                                                                        [100%]
1 passed in 9.46s
```

---

## G2 — a stray mention of the retired phase name in a non-allowlisted plugin file is refused (`test_no_fixer_phase_c1l9a.py`, axis: the allowlist)

- neutralization: one line, `<!-- probe: dispatch-fixer -->`, appended after the last line of
  `plugins/superheroes/rubric/glossary.md`.
- detector: `test_no_fixer_phase_c1l9a.py::test_a6_the_retired_phase_name_stands_only_where_the_allowlist_says`
- raw red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_a6_the_retired_phase_name_stands_only_where_the_allowlist_says ______

    def test_a6_the_retired_phase_name_stands_only_where_the_allowlist_says():
        found = {}
        for path in _non_test_files():
            with open(path, encoding="utf-8", errors="replace") as fh:
                count = fh.read().count(_RETIRED)
            if count:
                found[os.path.relpath(path, _PLUGIN_ROOT)] = count
        stray = sorted(rel for rel in found if rel not in _ALLOWED)
>       assert not stray, "the retired phase name stands in %s" % stray
E       AssertionError: the retired phase name stands in ['rubric/glossary.md']
E       assert not ['rubric/glossary.md']

/home/user/wt-2213-wo4a/plugins/superheroes/lib/tests/test_no_fixer_phase_c1l9a.py:95: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_no_fixer_phase_c1l9a.py::test_a6_the_retired_phase_name_stands_only_where_the_allowlist_says
1 failed in 1.50s
```

- restore: the inverse edit, the probe line removed.
- restore receipt: `git status --porcelain -- plugins/superheroes/rubric plugins/superheroes/lib/round_driver.py`
  printed nothing after the restore, and the file's last lines read:

```
### Check session

The one short cloud session that proves a [cloud setup](#cloud-setup).
```

- raw green (the whole absence file, which holds the detector):

```
bringing up nodes...
bringing up nodes...

......                                                                   [100%]
6 passed in 1.53s
```

---

Not proved by these two probes, and why: A1–A5 of the absence file each assert the absence of one named thing (a phase
constant, a template file, a lint kind, a contract, an order phase). They are detectors of a name coming back, and
each is protected only by that assertion's own reading; this order named no neutralization for them (the order
declared G1 and G2 only), and a neutralization for each would mean re-adding the production name, which lies outside
this order's surface. They are listed as unproven.
