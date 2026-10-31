# Bite-proof record — fix scope (work order 2, review C7 layer 2c)

Detector file: `plugins/superheroes/lib/tests/test_fix_scope_c7.py`, unedited between each red and its green. Every entry is a targeted, reversible edit to one production file, restored by the inverse edit (no `git checkout`, `restore`, `reset` or `stash`). Runs: `python3 -B -X pycache_prefix=/tmp/claude-0/pyc -m pytest '<exact node id>' -q -n 0`, one test node each, output captured whole. The five guarded elements are the five declared by the order; none is grouped.

## 1. The once-per-episode drop in `_queue_fix_batch` (`_drop_spent_out_of_scope_rows`, `lib/round_driver.py`)

- **Axis:** refusal of a repeat offer — a finding that is out of scope is left out of the fix batch of a later round of the same episode.
- **Detector:** `plugins/superheroes/lib/tests/test_fix_scope_c7.py::test_t1_a_critical_out_of_scope_finding_is_offered_to_a_fixer_once`.
- **Neutralization:** `round_driver.py`: `        if earlier:` followed by `            spent.append((key, row, earlier[0]))` became `        if False:` (same next line), so no row is ever spent.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_t1_a_critical_out_of_scope_finding_is_offered_to_a_fixer_once ______

captured_state = {'state': {'schemaVersion': 5, 'sessionGeneration': 4, 'config': {'leg': 'code', 'panel': False, 'code': True, 'vendors': ['claude', 'codex'], ...}, 'round': 4, ...}}

    def test_t1_a_critical_out_of_scope_finding_is_offered_to_a_fixer_once(captured_state):
        # axis: the fix batch of a later round in the same out-of-scope episode leaves the finding out
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo2_c7_fix_scope.md
        key = _key("Gate bypass")
        offers = []
    
        def reviewer(dim, tier, rnd, ctx):
            if rnd == 1 and dim == "code-reviewer":
                return {"findings": [_finding("Gate bypass", severity="Critical")]}
            return []
    
        def verifier(clusters, rnd):
            # the owner defers the finding before the first fix batch is planned
            if not captured_state["state"].get("rulingsLog"):
                _decide(captured_state["state"], key, "out-of-scope", rnd)
            return {"verdicts": [{"id": i, "verdict": "CONFIRMED", "evidence": "ran", "reason": "ran"}
                                 for c in (clusters or []) for i in (c.get("ids") or [])],
                    "vendor": "codex"}
    
        def fix_step(batch, rnd, payload):
            offers.append((rnd, [RD._fix_batch_row_key(r) for r in batch]))
            return {"fixes": [], "headDiff": TRD._headf(len(offers)), "changedSubjects": ["Code"]}
    
        def auditor(targets, rnd):
            return [{"id": t["id"], "ruling": "not-discharged", "reason": "still open"}
                    for t in (targets or [])]
    
        seams = TRD._seams(reviewer=reviewer, verifier=verifier, fix_step=fix_step, auditor=auditor,
                           io=<the retired owner-gate seam>)
        _result, state = TRD._run_loop_capturing_state(seams, TRD._cfg_cert())
        assert state["terminal"]
>       assert offers == [(1, [key])]  # offered once; the next round's batch left it out
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AssertionError: assert [(1, ['f.py::... bypass@L1'])] == [(1, ['f.py::... bypass@L1'])]
E         
E         Left contains 2 more items, first extra item: (2, ['f.py::gate bypass@L1'])
E         Use -v to get more diff

/home/user/wt-l2c/plugins/superheroes/lib/tests/test_fix_scope_c7.py:237: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_fix_scope_c7.py::test_t1_a_critical_out_of_scope_finding_is_offered_to_a_fixer_once
1 failed in 1.45s
exit=1
```

[The retired owner-gate seam's key is elided here; the seam was removed from the driver.]

- **Restore:** inverse edit (`if False:` back to `if earlier:`).
- **Restore receipt** (the restored lines, read back by `grep -n`):

```
        earlier = [rnd for rnd in offered if rnd != this_round]
        if earlier:
            spent.append((key, row, earlier[0]))
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 1.37s
exit=0
```

## 2. The `unnamedChange` refusal in `apply_audit_results` (`lib/audits.py`, both clearing branches)

- **Axis:** refusal — a clearing audit that names an unnamed change is not credited `discharged` without an allowing ruling.
- **Detector:** `plugins/superheroes/lib/tests/test_fix_scope_c7.py::test_t3_a_fix_with_an_unnamed_change_is_not_fixed_and_returns_with_the_auditors_reason`.
- **Neutralization:** `audits.py`: both conditions `... and unnamed_text and fid not in allowed_ids:` became `... and unnamed_text and False:` (the `discharged` branch and the `discharged-but-new-issue` branch), so the refusal never fires.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t3_a_fix_with_an_unnamed_change_is_not_fixed_and_returns_with_the_auditors_reason _

captured_state = {'state': {'schemaVersion': 5, 'sessionGeneration': 4, 'config': {'leg': 'code', 'panel': False, 'code': True, 'vendors': ['claude', 'codex'], ...}, 'round': 2, ...}}

    def test_t3_a_fix_with_an_unnamed_change_is_not_fixed_and_returns_with_the_auditors_reason(
            captured_state):
        # axis: refusal — a clearing audit that names an unnamed change is not credited without a ruling
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo2_c7_fix_scope.md
        key, state, offers, seen_targets, history = _unnamed_change_loop(captured_state, allow=False)
        assert state["terminal"] == "converged"
        audit = state["rounds"]["2"]["audits"][0]
>       assert audit["ruling"] == "not-discharged"
E       AssertionError: assert 'discharged' == 'not-discharged'
E         
E         - not-discharged
E         ? ----
E         + discharged

/home/user/wt-l2c/plugins/superheroes/lib/tests/test_fix_scope_c7.py:383: AssertionError
=========================== short test summary info ============================
FAILED tests/test_fix_scope_c7.py::test_t3_a_fix_with_an_unnamed_change_is_not_fixed_and_returns_with_the_auditors_reason
1 failed in 1.43s
```

- **Restore:** inverse edit (`and False:` back to `and fid not in allowed_ids:`, both places).
- **Restore receipt** (the restored lines, read back by `grep -n`):

```
            if has_reason and unnamed_text and fid not in allowed_ids:
            if candidates and unnamed_text and fid not in allowed_ids:
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 1.07s
```

## 3. The `allowsChange` allowance (the driver's `change_allowed_ids`, `_fold_audits` in `lib/round_driver.py`)

- **Axis:** allowance — only a `guidance` decision with `allowsChange: true` lets an unnamed change stand.
- **Detector:** `plugins/superheroes/lib/tests/test_fix_scope_c7.py::test_t3_a_guidance_ruling_that_allows_the_change_keeps_the_fix_credited`.
- **Neutralization:** `round_driver.py`: `change_allowed_ids=change_allowed_ids)` became `change_allowed_ids=[])` in the `apply_audit_results` call, so no id is ever allowed.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_t3_a_guidance_ruling_that_allows_the_change_keeps_the_fix_credited ____

captured_state = {'state': {'schemaVersion': 5, 'sessionGeneration': 4, 'config': {'leg': 'code', 'panel': False, 'code': True, 'vendors': ['claude', 'codex'], ...}, 'round': 3, ...}}

    def test_t3_a_guidance_ruling_that_allows_the_change_keeps_the_fix_credited(captured_state):
        # axis: allowance — only a guidance ruling with allowsChange true lets the unnamed change stand
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo2_c7_fix_scope.md
        key, state, offers, seen_targets, _history = _unnamed_change_loop(captured_state, allow=True)
        assert state["terminal"] == "converged"
        audit = state["rounds"]["2"]["audits"][0]
>       assert audit["ruling"] == "discharged" and audit["allowedChange"] == UNNAMED
E       AssertionError: assert ('not-discharged' == 'discharged'
E         
E         - discharged
E         + not-discharged
E         ? ++++)

/home/user/wt-l2c/plugins/superheroes/lib/tests/test_fix_scope_c7.py:401: AssertionError
=========================== short test summary info ============================
FAILED tests/test_fix_scope_c7.py::test_t3_a_guidance_ruling_that_allows_the_change_keeps_the_fix_credited
1 failed in 1.17s
```

- **Restore:** inverse edit (`change_allowed_ids=[])` back to `change_allowed_ids=change_allowed_ids)`).
- **Restore receipt** (the restored lines, read back by `grep -n`):

```
                                         change_allowed_ids=change_allowed_ids)
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 1.41s
```

## 4. The scrubber carrying `unnamedChange` (`_scrub_ruling_object`, `lib/engine_adapter.py`)

- **Axis:** transport — the scrubber carries every optional audit member the contract declares.
- **Detector:** `plugins/superheroes/lib/tests/test_fix_scope_c7.py::test_t4_edge8_a_string_unnamed_change_arrives_in_the_scrubbed_ruling_record`.
- **Neutralization:** `engine_adapter.py`: the contract-derived list `for opt in contract.get("optional") or ():` became the three fixed names `for opt in ("newIssues", "evidence", "auditorVendor"):`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t4_edge8_a_string_unnamed_change_arrives_in_the_scrubbed_ruling_record __

    def test_t4_edge8_a_string_unnamed_change_arrives_in_the_scrubbed_ruling_record():
        # axis: transport — the scrubber carries every optional audit member the contract declares
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo2_c7_fix_scope.md
        branch = _native_ruling_branch(unnamedChange=UNNAMED)
        ok, why = ERC.validate(_ruling_schema(), {"result": branch})
        assert ok, why
        normalized = ED._normalize_native_review_branch_for_parser(branch)
        assert normalized["unnamedChange"] == UNNAMED
        parsed = EA._REVIEW_CONTRACT_PARSERS["ruling"](normalized, None)
        assert parsed["ok"] is True
>       assert parsed["ruling"]["unnamedChange"] == UNNAMED
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       KeyError: 'unnamedChange'

/home/user/wt-l2c/plugins/superheroes/lib/tests/test_fix_scope_c7.py:583: KeyError
=========================== short test summary info ============================
FAILED tests/test_fix_scope_c7.py::test_t4_edge8_a_string_unnamed_change_arrives_in_the_scrubbed_ruling_record
1 failed in 1.24s
```

- **Restore:** inverse edit (the three fixed names back to the contract-derived list).
- **Restore receipt** (the restored lines, read back by `grep -n`):

```
    for opt in contract.get("optional") or ():
        if opt in obj:
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 1.05s
```

## 5. The native normalizer dropping a null `unnamedChange` (`_normalize_native_ruling_branch`, `lib/engine_dispatch.py`)

- **Axis:** transport — a null optional audit member is read as absent, never a parse refusal.
- **Detector:** `plugins/superheroes/lib/tests/test_fix_scope_c7.py::test_t4_edge8_a_native_audit_branch_with_a_null_unnamed_change_normalizes_and_parses`.
- **Neutralization:** `engine_dispatch.py`: `_omit_null_optional_fields(branch, contract.get("optional") or ())` became `_omit_null_optional_fields(branch, ("newIssues", "evidence", "auditorVendor"))`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t4_edge8_a_native_audit_branch_with_a_null_unnamed_change_normalizes_and_parses _

    def test_t4_edge8_a_native_audit_branch_with_a_null_unnamed_change_normalizes_and_parses():
        # axis: transport — a null optional audit member is read as absent, never a forfeit
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo2_c7_fix_scope.md
        branch = _native_ruling_branch()
        assert branch["unnamedChange"] is None
        ok, why = ERC.validate(_ruling_schema(), {"result": branch})
        assert ok, why
        normalized = ED._normalize_native_review_branch_for_parser(branch)
>       assert "unnamedChange" not in normalized
E       AssertionError: assert 'unnamedChange' not in {'resultKind': 'ruling', 'findings': None, 'verdicts': None, 'grouping': None, ...}

/home/user/wt-l2c/plugins/superheroes/lib/tests/test_fix_scope_c7.py:567: AssertionError
=========================== short test summary info ============================
FAILED tests/test_fix_scope_c7.py::test_t4_edge8_a_native_audit_branch_with_a_null_unnamed_change_normalizes_and_parses
1 failed in 1.52s
```

- **Restore:** inverse edit (the three fixed names back to the contract-derived list).
- **Restore receipt** (the restored lines, read back by `grep -n`):

```
    return _omit_null_optional_fields(branch, contract.get("optional") or ())
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 1.09s
```
