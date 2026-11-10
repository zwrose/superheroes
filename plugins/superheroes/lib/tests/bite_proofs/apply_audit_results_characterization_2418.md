# Bite-proof record — characterization of `audits.apply_audit_results` (#2418, order 2418-A)

Detector file: `plugins/superheroes/lib/tests/test_apply_audit_results_characterization_2418.py` (with its golden `plugins/superheroes/lib/tests/fixtures/apply_audit_results_golden_2418.json`), unedited between each red and its green. Every entry is a targeted, reversible Edit-tool edit to one production file (`plugins/superheroes/lib/audits.py`), restored by the inverse edit (no `git checkout`, `restore`, `reset` or `stash`). Runs: `scripts/pinned-python -B -X pycache_prefix=/tmp/pyc-2418 -m pytest '<exact node id>' -q -n 0 -p no:cacheprovider`, one test node each, output captured whole, followed by the `exit=` line the command printed. The `UV_NATIVE_TLS` deprecation warning that `uv` prints first is the only line left out of each capture. The five guarded elements (G1-G5) are the ones the order declared; none is grouped. Each `old_string` occurred exactly once (the Edit tool refuses a non-unique match). No secrets, tokens, private URLs or PII appear in any capture; nothing was redacted. After all five restores `git diff --stat -- plugins/superheroes/lib/audits.py` printed nothing.

The detectors are the tests that carry a `# bite-proof:` line.

## G1. The duplicate-target branch of the silence path (`audits.py` line 531)

- **Axis:** a duplicated target id with no result reads "duplicate audit target id — honoring none".
- **Detector:** `test_apply_audit_results_characterization_2418.py::test_t1_a_duplicated_target_id_with_no_result_reads_duplicate_target`.
- **Neutralization:** `if fid is not None and fid in duplicate_target_ids:` became `if False and fid in duplicate_target_ids:` at line 531 only (matched with its 12 leading spaces and the next line `                base.update(ruling="not-discharged",`).

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_t1_a_duplicated_target_id_with_no_result_reads_duplicate_target _____

    def test_t1_a_duplicated_target_id_with_no_result_reads_duplicate_target():
        # axis: a duplicated target id with no result reads "duplicate audit target id — honoring none"
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/apply_audit_results_characterization_2418.md
        out = audits.apply_audit_results([_target("d1"), _target("d1", line=9)], [])
        assert [e["ruling"] for e in out["audits"]] == ["not-discharged", "not-discharged"]
>       assert [e["reason"] for e in out["audits"]] == ["duplicate audit target id — honoring none"] * 2
E       AssertionError: assert ['more than o...onoring none'] == ['duplicate a...onoring none']
E         
E         At index 0 diff: 'more than one audit result claimed this finding — honoring none' != 'duplicate audit target id — honoring none'
E         Use -v to get more diff

/home/user/wt-2418/plugins/superheroes/lib/tests/test_apply_audit_results_characterization_2418.py:241: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_apply_audit_results_characterization_2418.py::test_t1_a_duplicated_target_id_with_no_result_reads_duplicate_target
1 failed in 0.21s
exit=1
```

- **Restore:** inverse edit (`if False and fid in duplicate_target_ids:` back to `if fid is not None and fid in duplicate_target_ids:`).
- **Restore receipt** (read back by the Grep tool, `duplicate_target_ids:$`):

```
531:            if fid is not None and fid in duplicate_target_ids:
547:        if fid is not None and fid in duplicate_target_ids:
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.22s
exit=0
```

## G2. The allowed-change record in the `discharged-but-new-issue` arm (`audits.py` line 822)

- **Axis:** an allowed unnamed change on a `discharged-but-new-issue` result is recorded as `allowedChange`.
- **Detector:** `test_apply_audit_results_characterization_2418.py::test_t2_an_allowed_unnamed_change_on_a_new_issue_result_is_recorded_as_allowed_change`.
- **Neutralization:** `elif unnamed_text:` became `elif False:` at line 822 only (matched together with the next two lines, `                    base["allowedChange"] = unnamed_text` and `                base.update(ruling="discharged-but-new-issue",`).

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t2_an_allowed_unnamed_change_on_a_new_issue_result_is_recorded_as_allowed_change _

    def test_t2_an_allowed_unnamed_change_on_a_new_issue_result_is_recorded_as_allowed_change():
        # axis: an allowed unnamed change on a discharged-but-new-issue result is recorded as `allowedChange`
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/apply_audit_results_characterization_2418.md
        result = _result("t1", ruling="discharged-but-new-issue", unnamedChange="  %s  " % UNNAMED,
                         newIssues=[_issue("fresh")])
        out = audits.apply_audit_results([_target("t1")], [result], change_allowed_ids=["t1"])
        (entry,) = out["audits"]
        assert entry["ruling"] == "discharged-but-new-issue"
>       assert entry["allowedChange"] == UNNAMED
               ^^^^^^^^^^^^^^^^^^^^^^
E       KeyError: 'allowedChange'

/home/user/wt-2418/plugins/superheroes/lib/tests/test_apply_audit_results_characterization_2418.py:255: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_apply_audit_results_characterization_2418.py::test_t2_an_allowed_unnamed_change_on_a_new_issue_result_is_recorded_as_allowed_change
1 failed in 0.20s
exit=1
```

- **Restore:** inverse edit (`elif False:` back to `elif unnamed_text:`).
- **Restore receipt** (read back by the Grep tool, `elif unnamed_text:`):

```
789:                elif unnamed_text:
790-                    base["allowedChange"] = unnamed_text
791-                base.update(ruling="discharged", reason=reason.strip())
--
822:                elif unnamed_text:
823-                    base["allowedChange"] = unnamed_text
824-                base.update(ruling="discharged-but-new-issue",
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.18s
exit=0
```

## G3. The unknown-ruling reason text (`audits.py` line 869)

- **Axis:** every arm's reason text is pinned by the golden table (the unknown-ruling arm is the representative).
- **Detector:** `test_apply_audit_results_characterization_2418.py::test_golden_scenario_returns_exactly_the_recorded_value[S29_unknown_ruling]`.
- **Neutralization:** `"unrecognized ruling %r — treated as not-discharged"` became `"unknown ruling %r — treated as not-discharged"`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_golden_scenario_returns_exactly_the_recorded_value[S29_unknown_ruling] __

scenario = {'name': 'S29_unknown_ruling', 'audited': [{'id': 't1', 'file': 'src/a.py', 'line': 2, 'title': 'Retry without a cap',... 'why': 'checked: brokeNothing'}, 'testWouldFail': {'answer': 'yes', 'why': 'checked: testWouldFail'}}}], 'kwargs': {}}

    @pytest.mark.parametrize("scenario", SCENARIOS, ids=[s["name"] for s in SCENARIOS])
    def test_golden_scenario_returns_exactly_the_recorded_value(scenario):
        # axis: the whole returned value (every list, its order, every audit key) equals the recorded golden
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/apply_audit_results_characterization_2418.md
        golden = _golden()
        assert scenario["name"] in golden, "scenario %s has no golden entry — regenerate" % scenario["name"]
>       assert _run(scenario) == golden[scenario["name"]]
E       AssertionError: assert {'audits': [{...ues': [], ...} == {'ambiguous':...ged': [], ...}
E         
E         Omitting 16 identical items, use -vv to show
E         Differing items:
E         {'audits': [{'id': 't1', 'identity': 'src/a.py::retry without a cap', 'file': 'src/a.py', 'line': 2, ...}]} != {'audits': [{'classKey': None, 'dimension': None, 'file': 'src/a.py', 'id': 't1', ...}]}
E         Use -v to get more diff

/home/user/wt-2418/plugins/superheroes/lib/tests/test_apply_audit_results_characterization_2418.py:270: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_apply_audit_results_characterization_2418.py::test_golden_scenario_returns_exactly_the_recorded_value[S29_unknown_ruling]
1 failed in 0.19s
exit=1
```

- **Restore:** inverse edit (`"unknown ruling %r — treated as not-discharged"` back to `"unrecognized ruling %r — treated as not-discharged"`).
- **Restore receipt:** no separate read-back was taken for this element; the evidence is the green run below and the empty `git diff --stat -- plugins/superheroes/lib/audits.py` after all restores (the whole file is byte-identical to base).

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.18s
exit=0
```

## G4. Target iteration order (`audits.py` line 498)

- **Axis:** the order of every list across targets is pinned by the golden table.
- **Detector:** `test_apply_audit_results_characterization_2418.py::test_golden_scenario_returns_exactly_the_recorded_value[M1_unsorted_targets_results_in_another_order_mixed_outcomes]`.
- **Neutralization:** `for f in audited:` became `for f in list(reversed(audited)):` at line 498 only (matched with the next four lines, ending `        if not isinstance(fid, str):`).

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_golden_scenario_returns_exactly_the_recorded_value[M1_unsorted_targets_results_in_another_order_mixed_outcomes] _

scenario = {'name': 'M1_unsorted_targets_results_in_another_order_mixed_outcomes', 'audited': [{'id': 't5', 'file': 'src/a.py', '...': 'checked: brokeNothing'}, 'testWouldFail': {'answer': 'yes', 'why': 'checked: testWouldFail'}}}, ...], 'kwargs': {}}

    @pytest.mark.parametrize("scenario", SCENARIOS, ids=[s["name"] for s in SCENARIOS])
    def test_golden_scenario_returns_exactly_the_recorded_value(scenario):
        # axis: the whole returned value (every list, its order, every audit key) equals the recorded golden
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/apply_audit_results_characterization_2418.md
        golden = _golden()
        assert scenario["name"] in golden, "scenario %s has no golden entry — regenerate" % scenario["name"]
>       assert _run(scenario) == golden[scenario["name"]]
E       AssertionError: assert {'audits': [{...', ...}], ...} == {'ambiguous':...', 't2'], ...}
E         
E         Omitting 13 identical items, use -vv to show
E         Differing items:
E         {'malformed': ['t3', 't7']} != {'malformed': ['t7', 't3']}
E         {'discharged': ['t2', 't5']} != {'discharged': ['t5', 't2']}
E         {'audits': [{'id': 't3', 'identity': 'src/a.py::retry without a cap', 'file': 'src/a.py', 'line': 2, ...}, {'id': 't7'...a.py', 'line': 2, ...}, {'id': 't5', 'identity': 'src/a.py::retry without a cap', 'file': 'src/a.py', 'line': 2, ...}]} != {'audits': [{'classKey': None, 'dimension': None, 'file': 'src/a.py', 'id': 't5', ...}, {'classKey': None, 'dimension'...one, 'file': 'src/a.py', 'id': 't...
E         
E         ...Full output truncated, use '-vv' to show

/home/user/wt-2418/plugins/superheroes/lib/tests/test_apply_audit_results_characterization_2418.py:270: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_apply_audit_results_characterization_2418.py::test_golden_scenario_returns_exactly_the_recorded_value[M1_unsorted_targets_results_in_another_order_mixed_outcomes]
1 failed in 0.21s
exit=1
```

(The `...Full output truncated, use '-vv' to show` line is pytest's own; nothing was elided from the capture by hand.)

- **Restore:** inverse edit (`for f in list(reversed(audited)):` back to `for f in audited:`).
- **Restore receipt** (read back by the Grep tool, `for f in (audited|list\(reversed)`):

```
440:    for f in audited:
498:    for f in audited:
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.19s
exit=0
```

## G5. Per-target reset of `guarded` (`audits.py` line 717)

- **Axis:** a `review-guarded` clear never leaks to the next target.
- **Detector:** `test_apply_audit_results_characterization_2418.py::test_golden_scenario_returns_exactly_the_recorded_value[M2_review_guarded_then_plain_then_plain_then_guarded]`.
- **Neutralization:** `guarded = None` became `guarded = locals().get("guarded")`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_golden_scenario_returns_exactly_the_recorded_value[M2_review_guarded_then_plain_then_plain_then_guarded] _

scenario = {'name': 'M2_review_guarded_then_plain_then_plain_then_guarded', 'audited': [{'id': 'g1', 'file': 'src/a.py', 'line': ...ecked: brokeNothing'}, 'testWouldFail': {'answer': 'review-guarded', 'why': 'checked: testWouldFail'}}}], 'kwargs': {}}

    @pytest.mark.parametrize("scenario", SCENARIOS, ids=[s["name"] for s in SCENARIOS])
    def test_golden_scenario_returns_exactly_the_recorded_value(scenario):
        # axis: the whole returned value (every list, its order, every audit key) equals the recorded golden
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/apply_audit_results_characterization_2418.md
        golden = _golden()
        assert scenario["name"] in golden, "scenario %s has no golden entry — regenerate" % scenario["name"]
>       assert _run(scenario) == golden[scenario["name"]]
E       AssertionError: assert {'audits': [{...ues': [], ...} == {'ambiguous':...', 'g2'], ...}
E         
E         Omitting 15 identical items, use -vv to show
E         Differing items:
E         {'audits': [{'id': 'g1', 'identity': 'src/a.py::retry without a cap', 'file': 'src/a.py', 'line': 2, ...}, {'id': 'p1'...a.py', 'line': 2, ...}, {'id': 'g2', 'identity': 'src/a.py::retry without a cap', 'file': 'src/a.py', 'line': 2, ...}]} != {'audits': [{'classKey': None, 'dimension': None, 'file': 'src/a.py', 'id': 'g1', ...}, {'classKey': None, 'dimension'...one, 'file': 'src/a.py', 'id': 'p2', ...}, {'classKey': None, 'dimension': None, 'file': 'src/a.py', 'id': 'g2', ...}]}
E         {'reviewGuarded': ['g1', 'p1', '...
E         
E         ...Full output truncated, use '-vv' to show

/home/user/wt-2418/plugins/superheroes/lib/tests/test_apply_audit_results_characterization_2418.py:270: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_apply_audit_results_characterization_2418.py::test_golden_scenario_returns_exactly_the_recorded_value[M2_review_guarded_then_plain_then_plain_then_guarded]
1 failed in 0.29s
exit=1
```

(The `...Full output truncated, use '-vv' to show` line is pytest's own; nothing was elided from the capture by hand.)

- **Restore:** inverse edit (`guarded = locals().get("guarded")` back to `guarded = None`).
- **Restore receipt** (read back by the Grep tool, `guarded = None`):

```
717:        guarded = None
718-        if ruling in _CLEARS and r["checks"]["testWouldFail"]["answer"] == REVIEW_GUARDED:
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.18s
exit=0
```

## Whole-file restore receipt

`git diff --stat -- plugins/superheroes/lib/audits.py`, run after the G5 restore (exit 0): no output, so `audits.py` is byte-identical to base.
