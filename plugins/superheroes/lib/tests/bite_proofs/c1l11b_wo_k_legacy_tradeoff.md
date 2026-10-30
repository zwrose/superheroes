# C1-L11b (WO-K) bite-proof — a carried row from a record written before `tradeoff` was persisted is held for the owner, never fixed autonomously

**Provenance:** implementer for WO-K, guarding `lib/round_driver.py` `_carried_findings`

Declared guarded element (from the order): K2 the `row.setdefault("tradeoff", True)` default in `round_driver._carried_findings` (the axis comment at `round_driver.py:1563` cites this record). It was neutralized with one targeted Edit and restored with the inverse Edit; no `git checkout`, `restore`, `reset` or `stash` was used. Run from `/home/user/wt-2266` (head `cbba2503` plus the uncommitted WO-K edits) under `timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-wo-k -m pytest <node ids> -q -p no:cacheprovider`. The captures are the runner's whole output for each run apart from the `UV_NATIVE_TLS` deprecation warning line, which is left out; nothing is redacted (no secrets, tokens or URLs appear in the captures).

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| K2 | `round_driver.py:1564` `row.setdefault("tradeoff", True)` in `_carried_findings` | a carried row with no `tradeoff` key is classified fail-closed, so `_hold_owner_choice` holds it for the owner when it is confirmed and blocking | `test_i3_a_carried_important_row_with_no_tradeoff_key_the_verifier_confirms_is_held_for_the_owner` |

Not separately neutralized (the unproven part of this record): the other half of the rule, that a row whose `tradeoff` key is present keeps its value, is pinned by `test_i3_a_carried_important_row_whose_tradeoff_key_is_false_still_reaches_the_fixer` and by T2's explicit `tradeoff=False` row. Neither has its own neutralization (an unconditional `row["tradeoff"] = True` would turn them red but was not run).

---

## K2 — the legacy-row default

**axis:** a carried row with no `tradeoff` key is classified fail-closed (`tradeoff: True`), so `_hold_owner_choice` holds it for the owner when it is confirmed and blocking.

**neutralization** (`round_driver.py`, `_carried_findings`: the default put back to the old falsy reading):
```python
-        row.setdefault("tradeoff", True)
+        row.setdefault("tradeoff", False)
```

**raw red:** `timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-wo-k -m pytest "plugins/superheroes/lib/tests/test_c1l11b_carried_findings.py::test_i3_a_carried_important_row_with_no_tradeoff_key_the_verifier_confirms_is_held_for_the_owner" -q -p no:cacheprovider`
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_i3_a_carried_important_row_with_no_tradeoff_key_the_verifier_confirms_is_held_for_the_owner _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-27/test_i3_a_carried_important_ro0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f192f574680>

    def test_i3_a_carried_important_row_with_no_tradeoff_key_the_verifier_confirms_is_held_for_the_owner(tmp_path, monkeypatch):
        finding = _finding(27)
        assert "tradeoff" not in finding
        key = finding[SC.FINDING_KEY_FIELD]
        s, (n, seen) = _confirmed_run(tmp_path, monkeypatch, finding)
>       assert RD.P_APPLY_FIXES not in [a for a, _ in seen], seen
E       AssertionError: [('dispatch-verifiers', 1), ('dispatch-synthesis', 1), ('apply-fixes', 1)]
E       assert 'apply-fixes' not in ['dispatch-verifiers', 'dispatch-synthesis', 'apply-fixes']
E        +  where 'apply-fixes' = RD.P_APPLY_FIXES

/home/user/wt-2266/plugins/superheroes/lib/tests/test_c1l11b_carried_findings.py:247: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11b_carried_findings.py::test_i3_a_carried_important_row_with_no_tradeoff_key_the_verifier_confirms_is_held_for_the_owner
1 failed in 5.43s
```

**restore:** the inverse edit — `False` put back to `True` in the `setdefault` call.

**restore receipt** (`grep -n 'row.setdefault("tradeoff"' plugins/superheroes/lib/round_driver.py`; the file also carries the other uncommitted WO-K edits, so `git status` over it is not a restore receipt here):
```
1564:        row.setdefault("tradeoff", True)
```

**raw green:** the same command.
```
.                                                                        [100%]
1 passed in 2.61s
```
