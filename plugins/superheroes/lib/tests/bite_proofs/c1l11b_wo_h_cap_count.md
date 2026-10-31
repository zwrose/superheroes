# C1-L11b (WO-H) bite-proof — the round cap holds the counted rounds as they stand, with no second extra-audit allowance

**Provenance:** implementer WO-H3, re-capturing WO-H's guard on `lib/review_record.py`, `lib/tests/test_c1l11b_lane_round_cap.py`

Declared guarded element (from the order): H1 `review_record._refuse_lane_over_round_cap`, the `if lane in _CAPPED_LANES and count > round_phases.ROUND_CAP:` line (the axis comment at `review_record.py:868` cites this record). It was neutralized with one targeted edit and restored with the inverse edit; no `git checkout`, `restore`, `reset` or `stash` was used. Run from `/home/user/wt-2266` (head `af12ff89`) under `timeout 600 scripts/pinned-python -B -m pytest <node ids> -q -p no:cacheprovider`. The captures are the runner's whole output for each run apart from the `UV_NATIVE_TLS` deprecation warning line, which is left out; nothing is redacted (no secrets, tokens or URLs appear in the captures).

| ID | Guarded element | Axis | Proving tests |
|---|---|---|---|
| H1 | `review_record.py:869` `_refuse_lane_over_round_cap`, the `if lane in _CAPPED_LANES and count > round_phases.ROUND_CAP:` line | the extra audit round is not allowed a second time on top of the count that already leaves it out | `test_e2_a_light_record_counts_at_most_the_cap_whether_or_not_it_ran_the_extra_audit_round` and `test_e3_the_micro_lane_follows_the_same_rule` |

Not separately neutralized (the unproven part of this record): the lane test (`lane in _CAPPED_LANES`) and the refusal itself (the guarded element of `c1l11b_wo_e_lane_round_cap.md`) are not neutralized here; the unknown-lane and full-lane no-cap edges (`test_e4`, `test_e5`) and the at-cap edge (`test_e6`) are not neutralized either. The neutralization below leaves the refusal in place and only widens the threshold, so the red proves the count term and nothing else.

---

## H1 — the count term of the round-cap check

**axis:** the extra audit round is not allowed a second time on top of the count that already leaves it out.

**neutralization** (`review_record.py`, `_refuse_lane_over_round_cap`: the extra audit round added back to the cap):
```python
-    if lane in _CAPPED_LANES and count > round_phases.ROUND_CAP:
+    if lane in _CAPPED_LANES and count > round_phases.ROUND_CAP + (1 if "extraAudit" in rounds else 0):
```

**raw red:** `timeout 600 scripts/pinned-python -B -m pytest plugins/superheroes/lib/tests/test_c1l11b_lane_round_cap.py::test_e2_a_light_record_counts_at_most_the_cap_whether_or_not_it_ran_the_extra_audit_round plugins/superheroes/lib/tests/test_c1l11b_lane_round_cap.py::test_e3_the_micro_lane_follows_the_same_rule -q -p no:cacheprovider`
```
F..F                                                                     [100%]
=================================== FAILURES ===================================
_ test_e2_a_light_record_counts_at_most_the_cap_whether_or_not_it_ran_the_extra_audit_round _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-13/test_e2_a_light_record_counts_0')

    def test_e2_a_light_record_counts_at_most_the_cap_whether_or_not_it_ran_the_extra_audit_round(tmp_path):
        # `rounds.count` already leaves the extra audit round out, so the cap is held to the count as it stands
        out, fake = _write(tmp_path, "light", CAP, extra=True)
        _written(out, fake)
        over, fake_over = _write(tmp_path, "light", CAP + 1, extra=True)
>       _refused(over, fake_over, "light", CAP + 1)

/home/user/wt-2266/plugins/superheroes/lib/tests/test_c1l11b_lane_round_cap.py:51: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

out = {'ok': True, 'action': 'created', 'url': 'http://c/1', 'parts': 0, ...}
fake = <test_review_record.Fake object at 0x7f074b62d340>, lane = 'light'
count = 5

    def _refused(out, fake, lane, count):
>       assert out["ok"] is False and out["reason"] == TOKEN, out
E       AssertionError: {'ok': True, 'action': 'created', 'url': 'http://c/1', 'parts': 0, ...}
E       assert (True is False)

/home/user/wt-2266/plugins/superheroes/lib/tests/test_c1l11b_lane_round_cap.py:31: AssertionError
__________ test_e3_the_micro_lane_follows_the_same_rule[5-True-False] __________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-13/test_e3_the_micro_lane_follows2')
count = 5, extra = True, written = False

    @pytest.mark.parametrize("count,extra,written", [(CAP + 1, False, False), (CAP, True, True), (CAP + 1, True, False)])
    def test_e3_the_micro_lane_follows_the_same_rule(tmp_path, count, extra, written):
        out, fake = _write(tmp_path, "micro", count, extra)
        if written:
            _written(out, fake)
        else:
>           _refused(out, fake, "micro", count)

/home/user/wt-2266/plugins/superheroes/lib/tests/test_c1l11b_lane_round_cap.py:61: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

out = {'ok': True, 'action': 'created', 'url': 'http://c/1', 'parts': 0, ...}
fake = <test_review_record.Fake object at 0x7f074ae12c30>, lane = 'micro'
count = 5

    def _refused(out, fake, lane, count):
>       assert out["ok"] is False and out["reason"] == TOKEN, out
E       AssertionError: {'ok': True, 'action': 'created', 'url': 'http://c/1', 'parts': 0, ...}
E       assert (True is False)

/home/user/wt-2266/plugins/superheroes/lib/tests/test_c1l11b_lane_round_cap.py:31: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c1l11b_lane_round_cap.py::test_e2_a_light_record_counts_at_most_the_cap_whether_or_not_it_ran_the_extra_audit_round
FAILED plugins/superheroes/lib/tests/test_c1l11b_lane_round_cap.py::test_e3_the_micro_lane_follows_the_same_rule[5-True-False]
2 failed, 2 passed in 0.33s
```

**restore:** the inverse edit — ` + (1 if "extraAudit" in rounds else 0)` removed from the condition.

**restore receipt** (`grep -n "if lane in _CAPPED_LANES" plugins/superheroes/lib/review_record.py`, then `git status --porcelain plugins/superheroes/lib/review_record.py`, which printed nothing):
```
869:    if lane in _CAPPED_LANES and count > round_phases.ROUND_CAP:
```

**raw green:** the same command.
```
....                                                                     [100%]
4 passed in 0.24s
```
