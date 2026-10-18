# Bite-proof record — fix audit: same-round fixes and reverts claims (#1956)

Detector file: `plugins/superheroes/lib/tests/test_fix_audit_same_round_1956.py`, unedited between each red and its green. Every entry is a targeted, reversible edit to one production file, restored by the inverse edit (no `git checkout`, `restore`, `reset` or `stash`). Runs: `scripts/pinned-python -B -X pycache_prefix=/tmp/claude-0/pyc -m pytest '<exact node id>' -q -n 0`, one test node each, output captured whole. The seven guarded elements are the seven declared by the order; none is grouped.

## 1. The fixes-claim membership in `_claims_verify` (`lib/audits.py`)

- **Axis:** the fixes claim must name a finding of the driver's own `roundFindings`.
- **Detector:** `plugins/superheroes/lib/tests/test_fix_audit_same_round_1956.py::test_a_fixes_claim_naming_an_id_outside_round_findings_is_refused`.
- **Neutralization:** `audits.py`: `all(i in round_ids for i in fixes)` became `all(True for i in fixes)`, so every fixes id verifies.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_a_fixes_claim_naming_an_id_outside_round_findings_is_refused _______

    def test_a_fixes_claim_naming_an_id_outside_round_findings_is_refused():
        # axis: the fixes claim must be a finding of the driver's own roundFindings
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/fix_audit_same_round_1956.md
>       _refused(_fold({"unnamedChange": UNNAMED, "unnamedChangeFixes": ["elsewhere"]}))

/home/user/superheroes/.wt-1956/plugins/superheroes/lib/tests/test_fix_audit_same_round_1956.py:114: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

out = {'audits': [{'id': 'a', 'identity': 'f.py::t', 'file': 'f.py', 'line': 1, ...}], 'discharged': ['a'], 'notDischarged': [], 'newIssues': [], ...}

    def _refused(out):
>       assert out["discharged"] == [] and out["notDischarged"] == ["a"]
E       AssertionError: assert (['a'] == []
E         
E         Left contains one more item: 'a'
E         Use -v to get more diff)

/home/user/superheroes/.wt-1956/plugins/superheroes/lib/tests/test_fix_audit_same_round_1956.py:58: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_fix_audit_same_round_1956.py::test_a_fixes_claim_naming_an_id_outside_round_findings_is_refused
1 failed in 5.31s
exit=1
```

- **Restore:** inverse edit (`all(True for i in fixes)` back to `all(i in round_ids for i in fixes)`).
- **Restore receipt** (the restored line, read back by `grep -n`):

```
136:    return all(i in round_ids for i in fixes) and all(x in refs for x in reverts)
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 3.59s
exit=0
```

## 2. The no-claim refusal in the `discharged` arm of `apply_audit_results` (`lib/audits.py`)

- **Axis:** an unclaimed unnamed change keeps today's refusal, same reason text and outcome list.
- **Detector:** `plugins/superheroes/lib/tests/test_fix_audit_same_round_1956.py::test_an_unnamed_change_with_no_claim_is_refused_though_the_record_has_candidates`.
- **Neutralization:** `audits.py`, the `if ruling == "discharged":` arm only: `... and fid not in allowed_ids and not attributed:` became `... and fid not in allowed_ids and not unnamed_text:`, so the refusal never fires and an unclaimed unnamed change is admitted. The `discharged-but-new-issue` arm is untouched.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_an_unnamed_change_with_no_claim_is_refused_though_the_record_has_candidates _

    def test_an_unnamed_change_with_no_claim_is_refused_though_the_record_has_candidates():
        # axis: an unclaimed unnamed change keeps today's refusal, same reason text and outcome list
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/fix_audit_same_round_1956.md
        out = _fold({"unnamedChange": UNNAMED})
>       _refused(out)

/home/user/superheroes/.wt-1956/plugins/superheroes/lib/tests/test_fix_audit_same_round_1956.py:98: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

out = {'audits': [{'id': 'a', 'identity': 'f.py::t', 'file': 'f.py', 'line': 1, ...}], 'discharged': ['a'], 'notDischarged': [], 'newIssues': [], ...}

    def _refused(out):
>       assert out["discharged"] == [] and out["notDischarged"] == ["a"]
E       AssertionError: assert (['a'] == []
E         
E         Left contains one more item: 'a'
E         Use -v to get more diff)

/home/user/superheroes/.wt-1956/plugins/superheroes/lib/tests/test_fix_audit_same_round_1956.py:58: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_fix_audit_same_round_1956.py::test_an_unnamed_change_with_no_claim_is_refused_though_the_record_has_candidates
1 failed in 2.73s
exit=1
```

- **Restore:** inverse edit (`and not unnamed_text:` back to `and not attributed:`).
- **Restore receipt** (the restored line, read back by `grep -n`):

```
428:            if has_reason and unnamed_text and fid not in allowed_ids and not attributed:
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 2.99s
exit=0
```

## 3. The reverts-claim ref membership in `_claims_verify` (`lib/audits.py`)

- **Axis:** the reverts claim must name a ref of the driver's own `reportedUnnamedChanges`.
- **Detector:** `plugins/superheroes/lib/tests/test_fix_audit_same_round_1956.py::test_a_reverts_claim_naming_a_ref_outside_reported_changes_is_refused`.
- **Neutralization:** `audits.py`: `all(x in refs for x in reverts)` became `all(True for x in reverts)`, so every ref verifies.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_a_reverts_claim_naming_a_ref_outside_reported_changes_is_refused _____

    def test_a_reverts_claim_naming_a_ref_outside_reported_changes_is_refused():
        # axis: the reverts claim must be a ref of the driver's own reportedUnnamedChanges
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/fix_audit_same_round_1956.md
>       _refused(_fold({"unnamedChange": UNNAMED, "unnamedChangeReverts": ["r9:a"]}))

/home/user/superheroes/.wt-1956/plugins/superheroes/lib/tests/test_fix_audit_same_round_1956.py:132: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

out = {'audits': [{'id': 'a', 'identity': 'f.py::t', 'file': 'f.py', 'line': 1, ...}], 'discharged': ['a'], 'notDischarged': [], 'newIssues': [], ...}

    def _refused(out):
>       assert out["discharged"] == [] and out["notDischarged"] == ["a"]
E       AssertionError: assert (['a'] == []
E         
E         Left contains one more item: 'a'
E         Use -v to get more diff)

/home/user/superheroes/.wt-1956/plugins/superheroes/lib/tests/test_fix_audit_same_round_1956.py:58: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_fix_audit_same_round_1956.py::test_a_reverts_claim_naming_a_ref_outside_reported_changes_is_refused
1 failed in 2.61s
exit=1
```

- **Restore:** inverse edit (`all(True for x in reverts)` back to `all(x in refs for x in reverts)`).
- **Restore receipt** (the restored line, read back by `grep -n`):

```
136:    return all(i in round_ids for i in fixes) and all(x in refs for x in reverts)
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 2.80s
exit=0
```

## 4. Each given claim must verify (`and` between the two `all(...)` checks, `lib/audits.py`)

- **Axis:** every claim given must verify — one failing claim refuses the whole result.
- **Detector:** `plugins/superheroes/lib/tests/test_fix_audit_same_round_1956.py::test_a_failing_fixes_claim_is_not_rescued_by_a_verifying_reverts_claim`.
- **Neutralization:** `audits.py`: `all(i in round_ids for i in fixes) and all(x in refs for x in reverts)` became `... or all(x in refs for x in reverts)`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_a_failing_fixes_claim_is_not_rescued_by_a_verifying_reverts_claim ____

    def test_a_failing_fixes_claim_is_not_rescued_by_a_verifying_reverts_claim():
        # axis: every claim given must verify — one failing claim refuses the whole result
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/fix_audit_same_round_1956.md
>       _refused(_fold({"unnamedChange": UNNAMED, "unnamedChangeFixes": ["elsewhere"],
                        "unnamedChangeReverts": ["r2:a"]}))

/home/user/superheroes/.wt-1956/plugins/superheroes/lib/tests/test_fix_audit_same_round_1956.py:154: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

out = {'audits': [{'id': 'a', 'identity': 'f.py::t', 'file': 'f.py', 'line': 1, ...}], 'discharged': ['a'], 'notDischarged': [], 'newIssues': [], ...}

    def _refused(out):
>       assert out["discharged"] == [] and out["notDischarged"] == ["a"]
E       AssertionError: assert (['a'] == []
E         
E         Left contains one more item: 'a'
E         Use -v to get more diff)

/home/user/superheroes/.wt-1956/plugins/superheroes/lib/tests/test_fix_audit_same_round_1956.py:58: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_fix_audit_same_round_1956.py::test_a_failing_fixes_claim_is_not_rescued_by_a_verifying_reverts_claim
1 failed in 2.69s
exit=1
```

- **Restore:** inverse edit (`or all(x in refs` back to `and all(x in refs`).
- **Restore receipt** (the restored line, read back by `grep -n`):

```
136:    return all(i in round_ids for i in fixes) and all(x in refs for x in reverts)
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 2.76s
exit=0
```

## 5. The owner-decision filter in `_audit_targets` (`lib/round_driver.py`)

- **Axis:** an owner skip / out-of-scope ruling takes a finding out of the attributable round findings.
- **Detector:** `plugins/superheroes/lib/tests/test_fix_audit_same_round_1956.py::test_audit_targets_leave_out_a_round_finding_the_owner_skipped`.
- **Neutralization:** `round_driver.py`: `if rdecision is not None and rdecision.get("ruling") not in _OWNER_FIX_RULINGS:` became `if False and rdecision is not None and ...`, so the `_OWNER_FIX_RULINGS` check never excludes a finding.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_audit_targets_leave_out_a_round_finding_the_owner_skipped ________

    def test_audit_targets_leave_out_a_round_finding_the_owner_skipped():
        # axis: an owner skip / out-of-scope ruling takes a finding out of the attributable round findings
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/fix_audit_same_round_1956.md
        state = _round_state(_finding("Stale comment", line=9, severity="Minor"),
                             _finding("Dead branch", line=12, severity="Minor"),
                             _finding("Wrong name", line=15, severity="Minor"),
                             _finding("Odd spacing", line=18, severity="Minor"))
        _decide(state, _key("Stale comment", 9), "out-of-scope", 1)
        _decide(state, _key("Wrong name", 15), "guidance", 1)
        RD._record_disposition(state, _key("Dead branch", 12), "refuted", 1, refutedReason="not a defect")
        (target,) = _targets(state)
        ids = [r["id"] for r in target["roundFindings"]]
>       assert ids == [_key("Wrong name", 15), _key("Odd spacing", 18)]
E       AssertionError: assert ['f.py::stale... spacing@L18'] == ['f.py::wrong... spacing@L18']
E         
E         At index 0 diff: 'f.py::stale comment@L9' != 'f.py::wrong name@L15'
E         Left contains one more item: 'f.py::odd spacing@L18'
E         Use -v to get more diff

/home/user/superheroes/.wt-1956/plugins/superheroes/lib/tests/test_fix_audit_same_round_1956.py:282: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_fix_audit_same_round_1956.py::test_audit_targets_leave_out_a_round_finding_the_owner_skipped
1 failed in 2.78s
exit=1
```

- **Restore:** inverse edit (`if False and rdecision is not None` back to `if rdecision is not None`).
- **Restore receipt** (the restored line, read back by `grep -n`):

```
5884:        if rdecision is not None and rdecision.get("ruling") not in _OWNER_FIX_RULINGS:
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 2.80s
exit=0
```

## 6. The legacy `" Unnamed change: "` branch in `_reported_unnamed_changes` (`lib/round_driver.py`)

- **Axis:** a session recorded before the structured key still yields its reported change.
- **Detector:** `plugins/superheroes/lib/tests/test_fix_audit_same_round_1956.py::test_history_reads_a_legacy_direct_not_discharged_reason`.
- **Neutralization:** `round_driver.py`: `elif (entry.get("ruling") == "not-discharged" and isinstance(reason, str)` became `elif (False and entry.get("ruling") == "not-discharged" and isinstance(reason, str)`, so the branch never runs.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_history_reads_a_legacy_direct_not_discharged_reason ___________

    def test_history_reads_a_legacy_direct_not_discharged_reason():
        # axis: a session recorded before the structured key still yields its reported change
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/fix_audit_same_round_1956.md
        state = _hist(r4=[{"id": "c", "ruling": "not-discharged",
                           "reason": "still wrong Unnamed change: does Z"}])
>       assert RD._reported_unnamed_changes(state) == [
            {"ref": "r4:c", "round": 4, "id": "c", "text": "does Z"}]
E       AssertionError: assert [] == [{'ref': 'r4:...t': 'does Z'}]
E         
E         Right contains one more item: {'ref': 'r4:c', 'round': 4, 'id': 'c', 'text': 'does Z'}
E         Use -v to get more diff

/home/user/superheroes/.wt-1956/plugins/superheroes/lib/tests/test_fix_audit_same_round_1956.py:341: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_fix_audit_same_round_1956.py::test_history_reads_a_legacy_direct_not_discharged_reason
1 failed in 2.67s
exit=1
```

- **Restore:** inverse edit (`elif (False and entry.get("ruling")` back to `elif (entry.get("ruling")`).
- **Restore receipt** (the restored lines, read back by `grep -n`):

```
5822:                elif (entry.get("ruling") == "not-discharged" and isinstance(reason, str)
5823-                        and " Unnamed change: " in reason):
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 2.53s
exit=0
```

## 7. The submit-guard claim check in `_audit_result_entry_fault` (`lib/round_driver.py`)

- **Axis:** the submit guard refuses a claim the fold would call malformed, by the same predicate.
- **Detector:** `plugins/superheroes/lib/tests/test_fix_audit_same_round_1956.py::test_the_submit_guard_refuses_a_malformed_claim[a string-unnamedChangeFixes]`.
- **Neutralization:** `round_driver.py`: `claim_field = audits.unnamed_change_claims_fault(...)` became `claim_field = None and audits.unnamed_change_claims_fault(...)`, so the guard sees no malformed claim.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_the_submit_guard_refuses_a_malformed_claim[a string-unnamedChangeFixes] _

field = 'unnamedChangeFixes', value = 'm'

    @pytest.mark.parametrize("field", ["unnamedChangeFixes", "unnamedChangeReverts"])
    @pytest.mark.parametrize("value", [v for v, _n in MALFORMED], ids=[n for _v, n in MALFORMED])
    def test_the_submit_guard_refuses_a_malformed_claim(field, value):
        # axis: the submit guard refuses a claim the fold would call malformed, by the same predicate
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/fix_audit_same_round_1956.md
        targets = [{"id": "a"}]
        ok = {"results": [{"id": "a", "ruling": "discharged", "reason": "fixed"}]}
        assert RD.audit_results_fault(ok, targets) is None
        for fine in (None, [], ["m"]):
            ok["results"][0][field] = fine
            assert RD.audit_results_fault(ok, targets) is None
        ok["results"][0][field] = value
        fault = RD.audit_results_fault(ok, targets)
>       assert fault and field in fault
E       assert (None)

/home/user/superheroes/.wt-1956/plugins/superheroes/lib/tests/test_fix_audit_same_round_1956.py:241: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_fix_audit_same_round_1956.py::test_the_submit_guard_refuses_a_malformed_claim[a string-unnamedChangeFixes]
1 failed in 2.49s
exit=1
```

- **Restore:** inverse edit (`claim_field = None and audits.unnamed_change_claims_fault(` back to `claim_field = audits.unnamed_change_claims_fault(`).
- **Restore receipt** (the restored lines, read back by `grep -n`):

```
5216:    claim_field = audits.unnamed_change_claims_fault(entry.get("unnamedChangeFixes"),
5217-                                                     entry.get("unnamedChangeReverts"))
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 2.89s
exit=0
```
