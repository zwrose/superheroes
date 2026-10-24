# Bite-proof record — an audit-spawned finding rides the next audit as its own target (#2115)

Detector file: `plugins/superheroes/lib/tests/test_audit_spawned_riders_2115.py`, unedited between each red and its green. Every entry is a targeted, reversible edit to one production file (`plugins/superheroes/lib/round_driver.py`), restored by the inverse edit (no `git checkout`, `restore`, `reset` or `stash`). Runs: `scripts/pinned-python -B -X pycache_prefix=/tmp/claude-0/pyc -m pytest '<exact node id>' -q -n 0`, one test node each, output captured whole; the `UV_NATIVE_TLS` deprecation warning that `uv` prints first is the only line left out of each capture. The three guarded elements are the three the order declared; none is grouped. Each target occurred exactly once in the edit's `old_string` (the Edit tool refuses a non-unique match).

The detectors the three entries name are the three tests that carry a `# bite-proof:` line. The other tests in the file carry an `# axis:` line only: their elements are outside the declared set and are listed under *Not proven* below.

## 1. Rider-target creation in `_audit_targets` (`lib/round_driver.py`)

- **Axis:** a child an audit raised, whose parent a later fix batch carries again, is an audit target of its own (`spawnedFrom`), so it is audited under its own key.
- **Detector:** `plugins/superheroes/lib/tests/test_audit_spawned_riders_2115.py::test_t1_a_child_the_audit_raised_and_a_later_audit_discharged_is_fixed_not_left_for_the_owner` (the #2105 replay).
- **Neutralization:** `round_driver.py`, in `_audit_targets`: `riders = _spawned_riders(state, ledger_by_key, _fault, batch_keys)` became `riders = []`, so no rider row (and no rider round-findings entry) is ever built.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t1_a_child_the_audit_raised_and_a_later_audit_discharged_is_fixed_not_left_for_the_owner _

captured_state = {'state': {'schemaVersion': 5, 'sessionGeneration': 6, 'config': {'leg': 'code', 'panel': False, 'code': True, 'vendors': ['claude', 'codex'], ...}, 'round': 3, ...}}
tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-2/test_t1_a_child_the_audit_rais0')

    def test_t1_a_child_the_audit_raised_and_a_later_audit_discharged_is_fixed_not_left_for_the_owner(
            captured_state, tmp_path):
        # axis: the #2105 replay end to end — the rider is audited under its own key and recorded fixed
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_spawned_riders_2115.md
        state, offers, seen = _spawn_loop()
        assert state["terminal"] == "converged", state.get("certification")
        assert state["auditSpawned"] == {X_KEY: P_KEY}
        assert offers == [(1, [P_KEY]), (2, [P_KEY])]  # the rider never joined a fix batch
        (_rnd, targets), = [s for s in seen if s[0] == 3]
>       assert [t["id"] for t in targets] == [P_KEY, X_KEY]
E       AssertionError: assert ['f.py::null deref@L1'] == ['f.py::null ...e comment@L2']
E         
E         Right contains one more item: 'f.py::stale comment@L2'
E         Use -v to get more diff

/home/user/wt-2115/plugins/superheroes/lib/tests/test_audit_spawned_riders_2115.py:105: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_spawned_riders_2115.py::test_t1_a_child_the_audit_raised_and_a_later_audit_discharged_is_fixed_not_left_for_the_owner
1 failed in 2.03s
exit=1
```

Disclosure of one extra run: the first inverse edit was refused (`riders = []` occurs twice in the file, once in `_spawned_riders`), and the test command, issued in the same turn, ran against the still-neutralized file. It printed the same red (`1 failed in 1.94s`, exit 1) and is not a second proof. The inverse edit was then re-issued with the next line as context and applied.

- **Restore:** inverse edit (`riders = []` back to `riders = _spawned_riders(state, ledger_by_key, _fault, batch_keys)`, keyed on the `for child, _parent, content in riders:` line below it).
- **Restore receipt** (the restored lines, read back by `grep -n "riders = "`; line 6151 is the unrelated local in `_spawned_riders`):

```
6041:    riders = _spawned_riders(state, ledger_by_key, _fault, batch_keys)
6151:    riders = []
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 2.05s
exit=0
```

## 2. The rider split in `_fold_audits` (`lib/round_driver.py`)

- **Axis:** a rider ruled anything but `discharged` leaves `notDischarged`, so it never joins the fix list, the stall breaker or the open-id set; it is left to the settle.
- **Detector:** `plugins/superheroes/lib/tests/test_audit_spawned_riders_2115.py::test_t2_a_rider_the_audit_does_not_discharge_is_left_for_the_owner_and_never_refixed`.
- **Neutralization:** `round_driver.py`, in `_fold_audits`: `outcome["notDischarged"] = [i for i in outcome["notDischarged"] if i not in rider_ids]` became `outcome["notDischarged"] = list(outcome["notDischarged"])`, so a not-discharged rider stays in `notDischarged` and the settle routes it into a fix batch.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t2_a_rider_the_audit_does_not_discharge_is_left_for_the_owner_and_never_refixed _

captured_state = {'state': {'schemaVersion': 5, 'sessionGeneration': 6, 'config': {'leg': 'code', 'panel': False, 'code': True, 'vendors': ['claude', 'codex'], ...}, 'round': 6, ...}}

    def test_t2_a_rider_the_audit_does_not_discharge_is_left_for_the_owner_and_never_refixed(
            captured_state):
        # axis: E1 — a rider ruled not-discharged has no disposition, is no fix, no breaker outcome, and is disclosed
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_spawned_riders_2115.md
        state, offers, seen = _spawn_loop(x_ruling="not-discharged")
>       assert state["terminal"] == "converged", state.get("certification")
E       AssertionError: {'shape': None, 'reason': 'owner chose to hold'}
E       assert 'held' == 'converged'
E         
E         - converged
E         + held

/home/user/wt-2115/plugins/superheroes/lib/tests/test_audit_spawned_riders_2115.py:128: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_spawned_riders_2115.py::test_t2_a_rider_the_audit_does_not_discharge_is_left_for_the_owner_and_never_refixed
1 failed in 2.12s
exit=1
```

- **Restore:** inverse edit (`list(outcome["notDischarged"])` back to the `[i for i in ... if i not in rider_ids]` comprehension).
- **Restore receipt** (the restored line, read back by `grep -n`):

```
6306:    outcome["notDischarged"] = [i for i in outcome["notDischarged"] if i not in rider_ids]
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 1.98s
exit=0
```

## 3. The post-compile anchor binding in `_fold_scoped` (`lib/round_driver.py`)

- **Axis:** the child-to-parent link is bound by compile anchor after the compile, so it survives a scoped candidate and an audit candidate sharing an anchor at equal severity (the compile keeps the scoped dict and the audit's `originAuditId` is lost).
- **Detector:** `plugins/superheroes/lib/tests/test_audit_spawned_riders_2115.py::test_t5_f3_an_equal_severity_scoped_candidate_does_not_lose_the_audits_link`. The same neutralization also reddens the T1 replay (no `auditSpawned`, so no rider target); only the F3 node was run for this entry.
- **Neutralization:** `round_driver.py`, in `_fold_scoped`: `_bind_audit_spawned(state, new_issues, compiled)` became `_bind_audit_spawned(state, new_issues, [])`, so no survivor is ever bound.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t5_f3_an_equal_severity_scoped_candidate_does_not_lose_the_audits_link __

    def test_t5_f3_an_equal_severity_scoped_candidate_does_not_lose_the_audits_link():
        # axis: F3 — the compile keeps the scoped dict at an equal-severity anchor; the link is bound by anchor
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/audit_spawned_riders_2115.md
        state = _scoped_state()
        survivors = RD.mechanical_compile([_child(), _audit_issue(P_KEY)], state["reviewedDiff"])[0]
        assert len(survivors) == 1 and "originAuditId" not in survivors[0]  # the audit's origin is gone
>       assert _fold_scoped(state, scoped=[_child()], issues=[_audit_issue(P_KEY)]) == {X_KEY: P_KEY}
E       AssertionError: assert None == {'f.py::stale comment@L2': 'f.py::null deref@L1'}
E        +  where None = _fold_scoped({'schemaVersion': 5, 'sessionGeneration': 6, 'config': {'leg': 'code', 'panel': False, 'code': True, 'vendors': ['claude', 'codex'], ...}, 'round': 2, ...}, scoped=[{'file': 'f.py', 'line': 2, 'title': 'Stale comment', 'severity': 'Minor', ...}], issues=[{'file': 'f.py', 'line': 2, 'title': 'Stale comment', 'severity': 'Minor', ...}])

/home/user/wt-2115/plugins/superheroes/lib/tests/test_audit_spawned_riders_2115.py:336: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_audit_spawned_riders_2115.py::test_t5_f3_an_equal_severity_scoped_candidate_does_not_lose_the_audits_link
1 failed in 1.76s
exit=1
```

- **Restore:** inverse edit (`_bind_audit_spawned(state, new_issues, [])` back to `_bind_audit_spawned(state, new_issues, compiled)`).
- **Restore receipt** (the restored lines, read back by `grep -n '_bind_audit_spawned('`; 6463 is the definition):

```
6463:def _bind_audit_spawned(state, new_issues, compiled):
6507:    _bind_audit_spawned(state, new_issues, compiled)
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 1.84s
exit=0
```

## Not proven (outside the declared set)

The order declared the three elements above. These other elements are asserted by tests in the file (each with an `# axis:` line) but have no neutralization and no red recorded here, so their protection is **unverified by a bite-proof**: the scoped-candidate origin strip in `_fold_scoped` (E6); the one-distinct-origin rule (E7); the `_spawned_riders` qualification clauses — current disposition, restage mark, merged, out-of-scope, summary row (E8); the absent or malformed spawn map (E9); the ledger-read-fault guard (E10); the ledger-only rider's round-findings entry (F2); the `auditRounds` and `prBodyAudited` exclusions and the `spawnedAudits` record in `_fold_audits`; the `still_open` addition for a rider left open.
