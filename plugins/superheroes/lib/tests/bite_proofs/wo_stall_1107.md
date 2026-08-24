# WO-STALL (#1107) bite-proofs — `_handle_stall` decomposition detectors

## BP1 — guard owner (`test_guard_owner_is_not_handle_stall`)

**Guarded element:** `state["selfRecovered"] = True` — axis: exactly one top-level owner, not `_handle_stall`.

**Neutralization:** moved assignment from `_commit_stall_self_recovery` into `_handle_stall`'s recovery branch.

**Command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_stall_decomposition.py::test_guard_owner_is_not_handle_stall -q -p no:randomly
```

**Red run:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________________ test_guard_owner_is_not_handle_stall _____________________
...
E       AssertionError: expected single guard owner _commit_stall_self_recovery, found: ['_handle_stall']
plugins/superheroes/lib/tests/test_stall_decomposition.py:75: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stall_decomposition.py::test_guard_owner_is_not_handle_stall
1 failed in 7.59s
```

**Restore:** removed `state["selfRecovered"] = True` from `_handle_stall`; restored line in `_commit_stall_self_recovery`.

**Restore receipt:** `_commit_stall_self_recovery` opens with `state["selfRecovered"] = True`; `_handle_stall` recovery branch calls `_commit_stall_self_recovery` without assigning `selfRecovered`.

**Green run:**
```
.                                                                        [100%]
1 passed in 0.10s
```

---

## BP2 — escalation owner (`test_escalation_owner_matches_guard_owner`)

**Guarded element:** `model_registry.escalate(...)` call — axis: exactly one top-level owner, same as guard owner.

**Neutralization:** replaced escalate call in `_commit_stall_self_recovery` with `rung = None`; added `model_registry.escalate(...)` in `_handle_stall` recovery branch.

**Command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_stall_decomposition.py::test_escalation_owner_matches_guard_owner -q -p no:randomly
```

**Red run:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
__________________ test_escalation_owner_matches_guard_owner ___________________
...
E       AssertionError: assert ['_handle_stall'] == ['_commit_sta...elf_recovery']
plugins/superheroes/lib/tests/test_stall_decomposition.py:86: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stall_decomposition.py::test_escalation_owner_matches_guard_owner
1 failed in 7.85s
```

**Restore:** removed `model_registry.escalate` from `_handle_stall`; restored full escalate block in `_commit_stall_self_recovery`.

**Restore receipt:** `_commit_stall_self_recovery` contains `rung = model_registry.escalate(fixer_vendor, _SELF_RECOVERY_FIXER_MODEL, _SELF_RECOVERY_FIXER_EFFORT)`.

**Green run:**
```
.                                                                        [100%]
1 passed in 0.10s
```

---

## BP3 — routing isolation (`test_handle_stall_has_no_terminal_routing`)

**Guarded element:** `_handle_stall` recovery branch — axis: no `_park_cannot_certify`, `_park_capped_open`, `_settle_delta_converged`, or `state["_fixBatch"]` assignment.

**Neutralization:** appended `_park_cannot_certify(state, "neutralized")` after `_route_stall_self_recovery` in `_handle_stall`.

**Command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_stall_decomposition.py::test_handle_stall_has_no_terminal_routing -q -p no:randomly
```

**Red run:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
__________________ test_handle_stall_has_no_terminal_routing ___________________
...
E       assert '_park_cannot_certify' not in 'def _handle... = P_STALL\n'
plugins/superheroes/lib/tests/test_stall_decomposition.py:94: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stall_decomposition.py::test_handle_stall_has_no_terminal_routing
1 failed in 0.11s
```

**Restore:** removed the appended `_park_cannot_certify` line from `_handle_stall`.

**Restore receipt:** `_handle_stall` recovery branch ends with `_route_stall_self_recovery(...); return` only.

**Green run:**
```
.                                                                        [100%]
1 passed in 0.10s
```

---

## BP4 — composition owner (`test_composition_owner_calls_stalled_open_targets`)

**Guarded element:** `_stalled_open_targets` call in recovery branch — axis: only `_compose_stall_fix_batch` calls it from recovery path.

**Neutralization:** added direct `_stalled_open_targets(state, breaker)` call in `_handle_stall` recovery branch before composition.

**Command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_stall_decomposition.py::test_composition_owner_calls_stalled_open_targets -q -p no:randomly
```

**Red run:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_composition_owner_calls_stalled_open_targets _______________
...
E       AssertionError: assert '_stalled_open_targets' not in '    if not s...n        return'
plugins/superheroes/lib/tests/test_stall_decomposition.py:109: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stall_decomposition.py::test_composition_owner_calls_stalled_open_targets
1 failed in 0.10s
```

**Restore:** removed the direct `_stalled_open_targets` call from `_handle_stall` recovery branch.

**Restore receipt:** `_recovery_branch_source` for `_handle_stall` contains no `_stalled_open_targets`; `_compose_stall_fix_batch` still calls it.

**Green run:**
```
.                                                                        [100%]
1 passed in 0.10s
```

---

## BP5 — routing totality (`test_routing_owner_is_total`)

**Guarded element:** `_route_stall_self_recovery` — axis: names all four routes (fixer, both parks, converge helpers).

**Neutralization:** deleted `_settle_delta_converged(state, config)` from the else branch of `_route_stall_self_recovery`.

**Command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_stall_decomposition.py::test_routing_owner_is_total -q -p no:randomly
```

**Red run:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_________________________ test_routing_owner_is_total __________________________
...
E       AssertionError: assert '_settle_delta_converged' in 'def _route_s...nfig)\n'
plugins/superheroes/lib/tests/test_stall_decomposition.py:116: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stall_decomposition.py::test_routing_owner_is_total
1 failed in 0.10s
```

**Restore:** restored `_settle_delta_converged(state, config)` in the else branch.

**Restore receipt:** `_route_stall_self_recovery` else branch contains both `_terminal_converged` (empty open set) and `_settle_delta_converged` (resolved path).

**Green run:**
```
.                                                                        [100%]
1 passed in 0.10s
```

---

## BP6 — attempt allocator (`test_reemit_of_an_unaccepted_wave_reuses_its_attempt`)

**Guarded element:** `_max_used_attempt` — axis: journal-only high-water; store landings must not advance re-emits.

**Neutralization:** inlined store scan into `_max_used_attempt` and returned `max(journal, store)`.

**Command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_round_wave_bookkeeping.py::test_reemit_of_an_unaccepted_wave_reuses_its_attempt -q -p no:randomly
```

**Red run:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_reemit_of_an_unaccepted_wave_reuses_its_attempt _____________
...
E       assert 1 == 0
plugins/superheroes/lib/tests/test_round_wave_bookkeeping.py:128: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_round_wave_bookkeeping.py::test_reemit_of_an_unaccepted_wave_reuses_its_attempt
1 failed in 0.39s
```

**Restore:** restored `_max_used_attempt` to `return _journal_max_attempt(session_dir, rnd, phase)` only.

**Restore receipt:** `_max_used_attempt` body is `return _journal_max_attempt(session_dir, rnd, phase)` with store-exclusion docstring.

**Green run:**
```
.                                                                        [100%]
1 passed in 0.12s
```

---

## BP7 — empty-resolution converge (`test_empty_resolution_converge_never_claims_an_unrun_panel`)

**Guarded element:** `_terminal_converged(..., full_panel=state.get("fullPanelRan"))` in `_route_stall_self_recovery` empty branch — axis: behavioural; certification fullPanel is carried from state, never hard-coded.

**Neutralization:** changed `full_panel=state.get("fullPanelRan")` to `full_panel=True` (hard-coded full-panel claim).

**Command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_stall_decomposition.py -q -p no:randomly
```

**Red run:**
```
.....F                                                                   [100%]
=================================== FAILURES ===================================
__________ test_empty_resolution_converge_never_claims_an_unrun_panel __________

    def test_empty_resolution_converge_never_claims_an_unrun_panel():
        # axis: behavioural — empty-resolution stall self-recovery converges via _terminal_converged
        # and carries fullPanel from state, never hard-codes a panel claim
        cfg = {"leg": "code", "vendors": ["claude", "codex"], "diff": "d", "fixerVendor": "claude"}
        breaker = {"reason": "audit-stall", "detail": "x", "stalledIdentities": ["v0"]}

        state_false = RD.new_state(cfg)
        state_false["fullPanelRan"] = False
        RD._handle_stall(state_false, state_false["config"], breaker)
        assert state_false["step"] == RD.P_TERMINAL
        assert state_false["terminal"] == "converged"
>       assert state_false["certification"]["fullPanel"] is False
E       assert True is False

plugins/superheroes/lib/tests/test_stall_decomposition.py:130: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stall_decomposition.py::test_empty_resolution_converge_never_claims_an_unrun_panel
1 failed, 5 passed in 19.48s
```

**Restore:** reverted `full_panel=True` to `full_panel=state.get("fullPanelRan")`.

**Restore receipt:** `_route_stall_self_recovery` empty branch reads `_terminal_converged(state, config, full_panel=state.get("fullPanelRan"))`.

**Green run:**
```
6 passed in 17.09s
```
