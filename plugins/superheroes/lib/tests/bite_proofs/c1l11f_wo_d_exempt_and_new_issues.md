# C1-L11f (WO-D) bite-proof — a not-discharged audit keeps the new issues it raised, on every arm that returns for it, and an abandoned session recovers them

**Provenance:** implementer WO-D2 (follow-up to WO-D of build #2279, C1-L11f), recording the guards D2 added in `lib/audits.py` (`apply_audit_results`) and `lib/review_record_session.py` (`_audit_candidates`), proved by `lib/tests/test_c1l11f_wo_d_exempt_and_new_issues.py`. D1's guard (the exemption filter in `_break_it_kept_step`) is K5 in `c1l11b_wo_k_carried_lost_test.md`, not here.

Each element was neutralized with one targeted Edit and restored by the inverse Edit; no `git checkout`, `restore`, `reset` or `stash` was used. Run from `/home/user/wt-2279-d` (build base `4f350065` plus the WO-D commit `2ac92236`) under `timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-wo-d2 -m pytest <node ids> -q -p no:cacheprovider`. Each capture is the runner's whole output for that run apart from the `UV_NATIVE_TLS` deprecation warning line (the first line of each real output), which is left out; nothing else is trimmed. Nothing is redacted: no secrets, tokens or URLs appear. The restore receipt of each element is the restored lines quoted back, together with `git diff --stat` printing nothing (empty output) over the tree after the restore.

Test nodes, all in `plugins/superheroes/lib/tests/test_c1l11f_wo_d_exempt_and_new_issues.py`:

- d1 = `test_d_a_not_discharged_audit_carrying_a_new_issue_stages_it_for_the_verifier`
- d2 = `test_d_the_driver_fold_stages_the_not_discharged_audits_new_issue_in_the_state`
- e = `test_e_a_not_discharged_audit_on_a_blocked_test_path_keeps_its_new_issue` (cases `[missing]`, `[changed-unexplained]`, `[weakened]`)
- g = `test_g_a_stored_audit_result_with_a_new_issue_abandoned_before_the_fold_shows_it_open` (cases `[not-discharged]`, `[discharged-but-new-issue]`) and `test_g_a_stored_result_that_is_not_a_not_discharged_or_new_issue_claim_adds_no_candidate` (6 cases)

Every red is the runner's own failure of the unedited test, caused by the neutralization alone, and on the axis the element claims.

| ID | Guarded element | Axis | Neutralization turns red | Stayed green under it |
|---|---|---|---|---|
| D-G1 | `apply_audit_results`, the `not-discharged` arm's keep (`audits.py:638`) | a not-discharged result's new issues are staged as a cleared audit's are | d1, d2 | e (all 3 cases) |
| D-G2 | `apply_audit_results`, the blocking-test-mismatch return's keep (`audits.py:484`) | the same, when the committed test is missing or changed with no explanation | e `[missing]`, e `[changed-unexplained]` | d1, d2, e `[weakened]` |
| D-G3 | `apply_audit_results`, the weakened-test return's keep (`audits.py:508`) | the same, when the test was weakened | e `[weakened]` | d1, d2, e `[missing]`, e `[changed-unexplained]` |
| D-G4 | `review_record_session._audit_candidates`, the widened ruling test (`review_record_session.py:711`) | an abandoned session's stored not-discharged result shows its new issues open in the record | g `[not-discharged]` | g `[discharged-but-new-issue]` and the 6 no-candidate cases |

The one blocking-test-mismatch return serves both the missing and the changed-unexplained cases, so D-G2 is one element with two red cases.

---

## D-G1 — the not-discharged arm's keep

**axis:** a `not-discharged` result that passed provenance joins `new_issues` as a `discharged-but-new-issue` one does.

**neutralization** (`audits.py:638`, the keep made unreachable):
```python
-            if keeps_new_issues:
+            if False:
                 new_issues.extend(_valid_new_issues(r.get("newIssues"), fid))
```

**raw red:** `timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-wo-d2 -m pytest <d1> <d2> <e> -q -p no:cacheprovider`
```
FF...                                                                    [100%]
=================================== FAILURES ===================================
_ test_d_a_not_discharged_audit_carrying_a_new_issue_stages_it_for_the_verifier _

    def test_d_a_not_discharged_audit_carrying_a_new_issue_stages_it_for_the_verifier():
        outcome = _fold([_raised()])
        assert outcome["notDischarged"] == ["t0"] and outcome["discharged"] == []
        assert AC._only(outcome)["ruling"] == "not-discharged" and AC._only(outcome)["reason"] == "the fix resolves it"
>       assert [(i["title"], i["originAuditId"]) for i in outcome["newIssues"]] == [(NEW_ISSUE["title"], "t0")]
E       AssertionError: assert [] == [('the fix br...aller', 't0')]
E         
E         Right contains one more item: ('the fix breaks the caller', 't0')
E         Use -v to get more diff

/home/user/wt-2279-d/plugins/superheroes/lib/tests/test_c1l11f_wo_d_exempt_and_new_issues.py:166: AssertionError
_ test_d_the_driver_fold_stages_the_not_discharged_audits_new_issue_in_the_state _

    def test_d_the_driver_fold_stages_the_not_discharged_audits_new_issue_in_the_state():
        cfg = {"repoRoot": "/nonexistent-review-project", "fixerVendor": "claude", "vendors": ["claude", "codex"]}
        state = RD.new_state(cfg)
        state["_verifyThen"] = RD.VERIFY_THEN_POST_AUDITS
        state["_auditTargets"] = [_target()]
        RD._fold_audits(state, cfg, {"results": [_raised()], "collectionManifest": {"t0": "codex"}})
>       assert [i["title"] for i in state["_newIssues"]] == [NEW_ISSUE["title"]]
E       AssertionError: assert [] == ['the fix breaks the caller']
E         
E         Right contains one more item: 'the fix breaks the caller'
E         Use -v to get more diff

/home/user/wt-2279-d/plugins/superheroes/lib/tests/test_c1l11f_wo_d_exempt_and_new_issues.py:178: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11f_wo_d_exempt_and_new_issues.py::test_d_a_not_discharged_audit_carrying_a_new_issue_stages_it_for_the_verifier
FAILED plugins/superheroes/lib/tests/test_c1l11f_wo_d_exempt_and_new_issues.py::test_d_the_driver_fold_stages_the_not_discharged_audits_new_issue_in_the_state
2 failed, 3 passed in 2.17s
```

**restore** (the inverse Edit): `audits.py:638`
```python
            if keeps_new_issues:
                new_issues.extend(_valid_new_issues(r.get("newIssues"), fid))
```
**restore receipt:** the lines above are the restored content at `audits.py:638`; `git diff --stat` after the restore printed nothing.

**raw green:** same command and nodes as the red.
```
.....                                                                    [100%]
5 passed in 1.84s
```

---

## D-G2 — the blocking-test-mismatch return's keep (missing and changed-unexplained)

**axis:** a `not-discharged` result whose committed break-it test is missing or changed with no explanation keeps the new issues it raised, though its fix is blocked.

**neutralization** (`audits.py:484`, the keep made unreachable; the edit's context lines `audits.append(base)` and `continue` follow it):
```python
-            if keeps_new_issues:
+            if False:
                 new_issues.extend(_valid_new_issues(r.get("newIssues"), fid))
             audits.append(base)
             continue
```

**raw red:** `timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-wo-d2 -m pytest <d1> <d2> <e> -q -p no:cacheprovider`
```
..FF.                                                                    [100%]
=================================== FAILURES ===================================
_ test_e_a_not_discharged_audit_on_a_blocked_test_path_keeps_its_new_issue[missing] _

path = 'missing'

    @pytest.mark.parametrize("path", ["missing", "changed-unexplained", "weakened"])
    def test_e_a_not_discharged_audit_on_a_blocked_test_path_keeps_its_new_issue(path):
        if path == "weakened":
            outcome = _fold([_raised(testMatch=WEAKENED)], _target("changed-explained"))
        else:
            outcome = _fold([_raised()], _target(path))
        assert outcome["notDischarged"] == ["t0"] and outcome["testMismatch"] == ["t0"]
        assert AC._only(outcome)["testMatch"]["blocking"] is True and AC._only(outcome)["ruling"] == "not-discharged"
>       assert _titles(outcome) == [NEW_ISSUE["title"]]
E       AssertionError: assert [] == ['the fix breaks the caller']
E         
E         Right contains one more item: 'the fix breaks the caller'
E         Use -v to get more diff

/home/user/wt-2279-d/plugins/superheroes/lib/tests/test_c1l11f_wo_d_exempt_and_new_issues.py:189: AssertionError
_ test_e_a_not_discharged_audit_on_a_blocked_test_path_keeps_its_new_issue[changed-unexplained] _

path = 'changed-unexplained'

    @pytest.mark.parametrize("path", ["missing", "changed-unexplained", "weakened"])
    def test_e_a_not_discharged_audit_on_a_blocked_test_path_keeps_its_new_issue(path):
        if path == "weakened":
            outcome = _fold([_raised(testMatch=WEAKENED)], _target("changed-explained"))
        else:
            outcome = _fold([_raised()], _target(path))
        assert outcome["notDischarged"] == ["t0"] and outcome["testMismatch"] == ["t0"]
        assert AC._only(outcome)["testMatch"]["blocking"] is True and AC._only(outcome)["ruling"] == "not-discharged"
>       assert _titles(outcome) == [NEW_ISSUE["title"]]
E       AssertionError: assert [] == ['the fix breaks the caller']
E         
E         Right contains one more item: 'the fix breaks the caller'
E         Use -v to get more diff

/home/user/wt-2279-d/plugins/superheroes/lib/tests/test_c1l11f_wo_d_exempt_and_new_issues.py:189: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11f_wo_d_exempt_and_new_issues.py::test_e_a_not_discharged_audit_on_a_blocked_test_path_keeps_its_new_issue[missing]
FAILED plugins/superheroes/lib/tests/test_c1l11f_wo_d_exempt_and_new_issues.py::test_e_a_not_discharged_audit_on_a_blocked_test_path_keeps_its_new_issue[changed-unexplained]
2 failed, 3 passed in 1.64s
```

**restore** (the inverse Edit): `audits.py:484`
```python
            if keeps_new_issues:
                new_issues.extend(_valid_new_issues(r.get("newIssues"), fid))
            audits.append(base)
            continue
```
**restore receipt:** the lines above are the restored content at `audits.py:484`; `git diff --stat` after the restore printed nothing.

**raw green:** same command and nodes as the red.
```
.....                                                                    [100%]
5 passed in 2.05s
```

---

## D-G3 — the weakened-test return's keep

**axis:** a `not-discharged` result whose break-it test was weakened keeps the new issues it raised, though its fix is blocked.

**neutralization** (`audits.py:508`, the keep made unreachable):
```python
-                if keeps_new_issues:
+                if False:
                     new_issues.extend(_valid_new_issues(r.get("newIssues"), fid))
                 audits.append(base)
                 continue
```

**raw red:** `timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-wo-d2 -m pytest <d1> <d2> <e> -q -p no:cacheprovider`
```
....F                                                                    [100%]
=================================== FAILURES ===================================
_ test_e_a_not_discharged_audit_on_a_blocked_test_path_keeps_its_new_issue[weakened] _

path = 'weakened'

    @pytest.mark.parametrize("path", ["missing", "changed-unexplained", "weakened"])
    def test_e_a_not_discharged_audit_on_a_blocked_test_path_keeps_its_new_issue(path):
        if path == "weakened":
            outcome = _fold([_raised(testMatch=WEAKENED)], _target("changed-explained"))
        else:
            outcome = _fold([_raised()], _target(path))
        assert outcome["notDischarged"] == ["t0"] and outcome["testMismatch"] == ["t0"]
        assert AC._only(outcome)["testMatch"]["blocking"] is True and AC._only(outcome)["ruling"] == "not-discharged"
>       assert _titles(outcome) == [NEW_ISSUE["title"]]
E       AssertionError: assert [] == ['the fix breaks the caller']
E         
E         Right contains one more item: 'the fix breaks the caller'
E         Use -v to get more diff

/home/user/wt-2279-d/plugins/superheroes/lib/tests/test_c1l11f_wo_d_exempt_and_new_issues.py:189: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11f_wo_d_exempt_and_new_issues.py::test_e_a_not_discharged_audit_on_a_blocked_test_path_keeps_its_new_issue[weakened]
1 failed, 4 passed in 2.10s
```

**restore** (the inverse Edit): `audits.py:508`
```python
                if keeps_new_issues:
                    new_issues.extend(_valid_new_issues(r.get("newIssues"), fid))
                audits.append(base)
                continue
```
**restore receipt:** the lines above are the restored content at `audits.py:508`; `git diff --stat` after the restore printed nothing.

**raw green:** same command and nodes as the red.
```
.....                                                                    [100%]
5 passed in 1.77s
```

---

## D-G4 — `_audit_candidates`' widened ruling test

**axis:** a stored fix-audit result with ruling `not-discharged` yields its new-issue candidates, so an abandoned session shows them open in the record.

**neutralization** (`review_record_session.py:711`, the widened test reverted to the one ruling):
```python
-    if not (isinstance(payload, dict) and payload.get("ruling") in ("discharged-but-new-issue", "not-discharged")):
+    if not (isinstance(payload, dict) and payload.get("ruling") == "discharged-but-new-issue"):
```

**raw red:** `timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-wo-d2 -m pytest <g, both functions> -q -p no:cacheprovider`
```
F.......                                                                 [100%]
=================================== FAILURES ===================================
_ test_g_a_stored_audit_result_with_a_new_issue_abandoned_before_the_fold_shows_it_open[not-discharged] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-116/test_g_a_stored_audit_result_w0')
ruling = 'not-discharged'

    @pytest.mark.parametrize("ruling", ["not-discharged", "discharged-but-new-issue"])
    def test_g_a_stored_audit_result_with_a_new_issue_abandoned_before_the_fold_shows_it_open(tmp_path, ruling):
        session = _audit_session(tmp_path, {"id": "t0", "ruling": ruling, "reason": "r", "newIssues": [dict(NEW_ISSUE)]})
        account = RS.account_from_session(session, extras(), Fake().readers(), abandoned="owner stopped the loop")
        rows = [f for f in account["findings"] if f["title"] == NEW_ISSUE["title"]]
>       assert len(rows) == 1, account["findings"]
E       AssertionError: []
E       assert 0 == 1
E        +  where 0 = len([])

/home/user/wt-2279-d/plugins/superheroes/lib/tests/test_c1l11f_wo_d_exempt_and_new_issues.py:244: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11f_wo_d_exempt_and_new_issues.py::test_g_a_stored_audit_result_with_a_new_issue_abandoned_before_the_fold_shows_it_open[not-discharged]
1 failed, 7 passed in 1.72s
```

**restore** (the inverse Edit): `review_record_session.py:711`
```python
    if not (isinstance(payload, dict) and payload.get("ruling") in ("discharged-but-new-issue", "not-discharged")):
```
**restore receipt:** the line above is the restored content at `review_record_session.py:711`; `git diff --stat` after the restore printed nothing.

**raw green:** same command and nodes as the red.
```
........                                                                 [100%]
8 passed in 1.98s
```

---

## Not separately neutralized (the unproven part of this record)

- `keeps_new_issues`' definition (`audits.py:462`): its `discharged-but-new-issue` leg and its provenance legs (`not provenance_enforced`, `bool(expected_auditor)`, `isinstance(collection_manifest, dict)`, `fid is not None`, `collection_manifest.get(fid) == expected_auditor`) were not neutralized. The `test_f_*` cases (unauthenticated and checks-fault results drop their new issues; malformed `newIssues` drop what they dropped before) ran green but were not run under a neutralization, so each leg is **unproven** as a separate guard.
- The three keeps D-G1 to D-G3 were each neutralized with `if False:`; a neutralization of `keeps_new_issues` itself (making all three keeps fail at once) was not run.
- D-G4: the `isinstance(raised, list)` and `isinstance(c, dict)` filters in `_audit_candidates` were not neutralized; the no-candidate cases in `g` pass against them but were not run under a neutralization.
- `round_driver`'s staging of `newIssues` needed no change (d2 pins that it stages what `apply_audit_results` returns); it was not neutralized.
