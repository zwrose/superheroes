# C1-L11b (WO-E) bite-proof — the record refuses a fifth round on the light and micro lanes

**Provenance:** implementer WO-E / `lib/review_record.py`, `lib/tests/test_c1l11b_lane_round_cap.py`

Declared guarded element (from the order): E1 `review_record._refuse_lane_over_round_cap`, the one condition that raises `review-record-round-cap-exceeded`. It was neutralized with one targeted edit and restored with the inverse edit; no `git checkout`, `restore`, `reset` or `stash` was used. Run from `/home/user/wt-2266-e` under `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest -q -p no:cacheprovider`. The captures are the runner's whole output for each run apart from the `UV_NATIVE_TLS` deprecation warning line, which is left out; nothing is redacted (no secrets, tokens or URLs appear in the captures).

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| E1 | `review_record.py` `_refuse_lane_over_round_cap`, the `if lane in _CAPPED_LANES and count > ...` line | a light or micro record never shows a round past the cap, except the one extra audit round | `test_e1_a_light_record_over_the_cap_without_the_extra_audit_round_is_refused` |

Not separately neutralized (the unproven part of this record): the extra-audit allowance (the `+ (1 if "extraAudit" in rounds else 0)` term) is covered by `test_e2` and `test_e3` but was not neutralized on its own; the unknown-lane and full-lane no-cap edges (`test_e4`, `test_e5`) and the at-cap edge (`test_e6`) are not neutralized either.

---

## E1 — the round-cap check

**axis:** a light or micro record never shows a round past the cap, except the one extra audit round.

**neutralization** (`review_record.py`, `_refuse_lane_over_round_cap`: the condition made `False`):
```python
-    if lane in _CAPPED_LANES and count > round_phases.ROUND_CAP + (1 if "extraAudit" in rounds else 0):
+    if False and lane in _CAPPED_LANES and count > round_phases.ROUND_CAP + (1 if "extraAudit" in rounds else 0):
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest -q -p no:cacheprovider plugins/superheroes/lib/tests/test_c1l11b_lane_round_cap.py -k e1`
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_e1_a_light_record_over_the_cap_without_the_extra_audit_round_is_refused _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-0/test_e1_a_light_record_over_th0')

    def test_e1_a_light_record_over_the_cap_without_the_extra_audit_round_is_refused(tmp_path):
        out, fake = _write(tmp_path, "light", CAP + 1)
>       _refused(out, fake, "light", CAP + 1)

/home/user/wt-2266-e/plugins/superheroes/lib/tests/test_c1l11b_lane_round_cap.py:43: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

out = {'ok': True, 'action': 'created', 'url': 'http://c/1', 'parts': 0, ...}
fake = <test_review_record.Fake object at 0x7f14b91b22a0>, lane = 'light'
count = 5

    def _refused(out, fake, lane, count):
>       assert out["ok"] is False and out["reason"] == TOKEN, out
E       AssertionError: {'ok': True, 'action': 'created', 'url': 'http://c/1', 'parts': 0, ...}
E       assert (True is False)

/home/user/wt-2266-e/plugins/superheroes/lib/tests/test_c1l11b_lane_round_cap.py:31: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11b_lane_round_cap.py::test_e1_a_light_record_over_the_cap_without_the_extra_audit_round_is_refused
1 failed, 9 deselected in 1.25s
```

**restore:** the inverse edit — `False and ` removed from the condition.

**restore receipt** (`grep -n "if lane in _CAPPED_LANES" plugins/superheroes/lib/review_record.py`):
```
857:    if lane in _CAPPED_LANES and count > round_phases.ROUND_CAP + (1 if "extraAudit" in rounds else 0):
```

**raw green:** the same command.
```
.                                                                        [100%]
1 passed, 9 deselected in 1.50s
```
