# Bite-proof record: nothing a slice reviewer left unread goes unreviewed

Detector: `plugins/superheroes/lib/tests/test_unread_waves_c2.py`. Guarded code: `_unread_of_wave`, `_open_unread_wave` and
`_after_panel_wave` in `plugins/superheroes/lib/round_driver.py`, `_fold_panel`'s wave merge in the same file, and
`wave_roster` in `plugins/superheroes/lib/round_phases.py`.

Every run below is the single test node named by `-k`, tests unedited, run as
`scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-wo -m pytest plugins/superheroes/lib/tests/test_unread_waves_c2.py -q -p no:cacheprovider -k <name>`,
followed in the same invocation by `git diff --stat`. The restore of every element is the inverse `Edit` of the neutralization
(the restored lines are quoted back under each entry); the `git diff --stat` printed after each restore is the supplementary
check. The tracked-file stat after every restore reads `round_driver.py | 175` lines changed, the same as before the
neutralization (the first neutralization was applied on top of 176 lines because it added a line, and the restore returned it to
175). The red of the pass-through noise line `warning: The UV_NATIVE_TLS ...` is the launcher's, not the test's. Nothing in
these captures is secret, so nothing is redacted.

## E1: the per-seat subtraction at the call site

- Guarded element: `_unread_of_wave` passes `read_lists` (each seat's own list) to `slicing.unread_obligations`. Axis: a seat
  that read nothing leaves its slice unread however much another seat of that slice read.
- Neutralization: replace `return slicing.unread_obligations(assigned, read_lists)` with
  `union = [p for v in read_lists.values() if isinstance(v, list) for p in v]` then
  `return slicing.unread_obligations(assigned, {seat: union for seat in assigned})`.
- Detector: `test_a_test_seat_that_read_nothing_opens_a_second_wave_over_its_slice_though_its_code_seat_read_everything`.
- Raw red:

```
 plugins/superheroes/lib/decision_kinds.py |   1 +
 plugins/superheroes/lib/round_driver.py   | 176 ++++++++++++++++++++++++++----
 plugins/superheroes/lib/round_phases.py   |  39 ++++++-
 3 files changed, 195 insertions(+), 21 deletions(-)
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_test_seat_that_read_nothing_opens_a_second_wave_over_its_slice_though_its_code_seat_read_everything _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-63/test_a_test_seat_that_read_not0')

    def test_a_test_seat_that_read_nothing_opens_a_second_wave_over_its_slice_though_its_code_seat_read_everything(tmp_path):
        state = _state(_repo(tmp_path), _three_thousand())
        sdir = _session_dir(tmp_path)
        _wave(state, reads={"test-role:s2": []})
>       assert state["step"] == RD.P_PANEL and state["_sliceWave"] == 2
E       AssertionError: assert ('dispatch-seams-check' == 'dispatch-panel'
E         
E         - dispatch-panel
E         + dispatch-seams-check)

/home/user/wt-2218-wo4/plugins/superheroes/lib/tests/test_unread_waves_c2.py:90: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_unread_waves_c2.py::test_a_test_seat_that_read_nothing_opens_a_second_wave_over_its_slice_though_its_code_seat_read_everything
1 failed, 18 deselected in 17.11s
```

- Restore: the inverse edit. Restored lines: `    return slicing.unread_obligations(assigned, read_lists)`.
- Raw green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 18 deselected in 0.60s
 plugins/superheroes/lib/decision_kinds.py |   1 +
 plugins/superheroes/lib/round_driver.py   | 175 ++++++++++++++++++++++++++----
 plugins/superheroes/lib/round_phases.py   |  39 ++++++-
 3 files changed, 194 insertions(+), 21 deletions(-)
```

## E2: the wave bound

- Guarded element: `if unread and wave < UNREAD_WAVE_BOUND and _open_unread_wave(...)` in `_after_panel_wave`. Axis: the waves
  stop after the third; nothing past it is opened.
- Neutralization: change `wave < UNREAD_WAVE_BOUND` to `wave < UNREAD_WAVE_BOUND + 1` (one more wave).
- Detector: `test_the_waves_stop_at_the_bound_and_what_is_still_unread_is_recorded_with_every_waves_findings_staged_once`.
- Raw red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_the_waves_stop_at_the_bound_and_what_is_still_unread_is_recorded_with_every_waves_findings_staged_once _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-65/test_the_waves_stop_at_the_bou0')

    def test_the_waves_stop_at_the_bound_and_what_is_still_unread_is_recorded_with_every_waves_findings_staged_once(tmp_path):
        state = _state(_repo(tmp_path), _three_thousand())
        _wave(state, reads={"test-role:s1": []}, findings={"code-reviewer:s1": [_finding("wave one bug")]})
        assert state["step"] == RD.P_PANEL and state["_sliceWave"] == 2
        _wave(state, reads=NOTHING, findings={"code-reviewer:w2u1": [_finding("wave two bug", line=6)]})
        assert state["step"] == RD.P_PANEL and state["_sliceWave"] == RD.UNREAD_WAVE_BOUND == 3
        assert RP.panel_roster(state, state["config"])[0] == "code-reviewer:w3u1"
        _wave(state, reads=NOTHING, findings={"code-reviewer:w3u1": [_finding("wave three bug", line=7)]})
>       assert state["step"] == RD.P_SEAMS
E       AssertionError: assert 'dispatch-panel' == 'dispatch-seams-check'
E         
E         - dispatch-seams-check
E         + dispatch-panel

/home/user/wt-2218-wo4/plugins/superheroes/lib/tests/test_unread_waves_c2.py:149: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_unread_waves_c2.py::test_the_waves_stop_at_the_bound_and_what_is_still_unread_is_recorded_with_every_waves_findings_staged_once
1 failed, 18 deselected in 0.62s
 plugins/superheroes/lib/decision_kinds.py |   1 +
 plugins/superheroes/lib/round_driver.py   | 175 ++++++++++++++++++++++++++----
 plugins/superheroes/lib/round_phases.py   |  39 ++++++-
 3 files changed, 194 insertions(+), 21 deletions(-)
```

- Restore: the inverse edit. Restored line: `    if unread and wave < UNREAD_WAVE_BOUND and _open_unread_wave(state, config, unread, wave, this_wave):`.
- Raw green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 18 deselected in 0.49s
 plugins/superheroes/lib/decision_kinds.py |   1 +
 plugins/superheroes/lib/round_driver.py   | 175 ++++++++++++++++++++++++++----
 plugins/superheroes/lib/round_phases.py   |  39 ++++++-
 3 files changed, 194 insertions(+), 21 deletions(-)
```

## E3: the premortem wave seat

- Guarded element: `round_phases.wave_roster(dims, marked, with_whole=bool(risky))` in `_open_unread_wave`. Axis: a wave
  holding a risk-touching unread slice seats one premortem reviewer over the whole change.
- Neutralization: change `with_whole=bool(risky)` to `with_whole=False` (never add it).
- Detector: `test_an_unread_part_that_touches_a_risk_area_gets_a_security_seat_and_one_premortem_seat_over_the_whole_change`.
- Raw red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_an_unread_part_that_touches_a_risk_area_gets_a_security_seat_and_one_premortem_seat_over_the_whole_change _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-67/test_an_unread_part_that_touch0')

    def test_an_unread_part_that_touches_a_risk_area_gets_a_security_seat_and_one_premortem_seat_over_the_whole_change(tmp_path):
        state = _state(_repo(tmp_path, RISK_AREAS), _risk_diff())
        sdir = _session_dir(tmp_path)
        touching = next(s for s in state["slicePlan"]["slices"] if any(p["file"] == PAYMENTS for p in s["parts"]))
        sid = touching["id"]
        _wave(state, reads={"%s:%s" % (lens, sid): [] for lens in RP.SLICED_LENSES})
        assert state["step"] == RD.P_PANEL
>       assert RP.panel_roster(state, state["config"]) == [
            "code-reviewer:w2u1", "test-role:w2u1", "security-reviewer:w2u1", "premortem-reviewer:w2"]
E       AssertionError: assert ['code-review...eviewer:w2u1'] == ['code-review...-reviewer:w2']
E         
E         Right contains one more item: 'premortem-reviewer:w2'
E         Use -v to get more diff

/home/user/wt-2218-wo4/plugins/superheroes/lib/tests/test_unread_waves_c2.py:115: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_unread_waves_c2.py::test_an_unread_part_that_touches_a_risk_area_gets_a_security_seat_and_one_premortem_seat_over_the_whole_change
1 failed, 18 deselected in 0.54s
 plugins/superheroes/lib/decision_kinds.py |   1 +
 plugins/superheroes/lib/round_driver.py   | 175 ++++++++++++++++++++++++++----
 plugins/superheroes/lib/round_phases.py   |  39 ++++++-
 3 files changed, 194 insertions(+), 21 deletions(-)
```

- Restore: the inverse edit. Restored line: `    roster = round_phases.wave_roster(dims, marked, with_whole=bool(risky))`.
- Raw green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 18 deselected in 0.50s
 plugins/superheroes/lib/decision_kinds.py |   1 +
 plugins/superheroes/lib/round_driver.py   | 175 ++++++++++++++++++++++++++----
 plugins/superheroes/lib/round_phases.py   |  39 ++++++-
 3 files changed, 194 insertions(+), 21 deletions(-)
```

## E4: the residual into `unreadShare`

- Guarded element: `residual = unread` before `slicing.unread_share(residual, ...)` in `_after_panel_wave`. Axis: what is
  still unread at the bound is recorded in the share, never dropped.
- Neutralization: change `residual = unread` to `residual = []`.
- Detector: the same bound test, at its `unreadLines` assertion.
- Raw red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_the_waves_stop_at_the_bound_and_what_is_still_unread_is_recorded_with_every_waves_findings_staged_once _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-69/test_the_waves_stop_at_the_bou0')

    def test_the_waves_stop_at_the_bound_and_what_is_still_unread_is_recorded_with_every_waves_findings_staged_once(tmp_path):
        state = _state(_repo(tmp_path), _three_thousand())
        _wave(state, reads={"test-role:s1": []}, findings={"code-reviewer:s1": [_finding("wave one bug")]})
        assert state["step"] == RD.P_PANEL and state["_sliceWave"] == 2
        _wave(state, reads=NOTHING, findings={"code-reviewer:w2u1": [_finding("wave two bug", line=6)]})
        assert state["step"] == RD.P_PANEL and state["_sliceWave"] == RD.UNREAD_WAVE_BOUND == 3
        assert RP.panel_roster(state, state["config"])[0] == "code-reviewer:w3u1"
        _wave(state, reads=NOTHING, findings={"code-reviewer:w3u1": [_finding("wave three bug", line=7)]})
        assert state["step"] == RD.P_SEAMS
        assert "_sliceWave" not in state and "_sliceCarry" not in state
        assert [i for i in _slice_ids(state) if i.startswith("w4")] == []
        share = state["unreadShare"]
>       assert share["unreadLines"] > 0 and share["unreadLines"] <= share["countableLines"]
E       assert (0 > 0)

/home/user/wt-2218-wo4/plugins/superheroes/lib/tests/test_unread_waves_c2.py:153: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_unread_waves_c2.py::test_the_waves_stop_at_the_bound_and_what_is_still_unread_is_recorded_with_every_waves_findings_staged_once
1 failed, 18 deselected in 0.60s
 plugins/superheroes/lib/decision_kinds.py |   1 +
 plugins/superheroes/lib/round_driver.py   | 175 ++++++++++++++++++++++++++----
 plugins/superheroes/lib/round_phases.py   |  39 ++++++-
 3 files changed, 194 insertions(+), 21 deletions(-)
```

- Restore: the inverse edit. Restored line: `    residual = unread`.
- Raw green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 18 deselected in 0.55s
 plugins/superheroes/lib/decision_kinds.py |   1 +
 plugins/superheroes/lib/round_driver.py   | 175 ++++++++++++++++++++++++++----
 plugins/superheroes/lib/round_phases.py   |  39 ++++++-
 3 files changed, 194 insertions(+), 21 deletions(-)
```

## E5: the merge of a later wave's `seatStatus`

- Guarded element: `_record_round(state, "seatStatus", {**prior_status, **seat_status})` in `_fold_panel`. Axis: a later wave's
  seat statuses are added to the first wave's, never written over them. The detector was added by this order (no earlier test
  asserts it).
- Neutralization: change the line to `_record_round(state, "seatStatus", seat_status)` (overwrite).
- Detector: `test_a_later_waves_fold_adds_to_the_first_waves_seat_status_coverage_and_review_record`.
- Raw red (the "Full output truncated" line is pytest's own):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_later_waves_fold_adds_to_the_first_waves_seat_status_coverage_and_review_record _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-71/test_a_later_waves_fold_adds_t0')

    def test_a_later_waves_fold_adds_to_the_first_waves_seat_status_coverage_and_review_record(tmp_path):
        state = _state(_repo(tmp_path), _three_thousand())
        first = _wave(state, reads={"test-role:s2": []})
        first_keys = set(first)
        status = dict(state["rounds"]["1"]["seatStatus"])
        assert set(status) == first_keys and set(status.values()) == {"run"}
        second = _wave(state)
        second_keys = set(second)
        rec = state["rounds"]["1"]
>       assert set(rec["seatStatus"]) == first_keys | second_keys and not first_keys & second_keys
E       AssertionError: assert ({'code-review...st-role:w2u1'} == {'architectur...eviewer', ...}
E         
E         Extra items in the right set:
E         'security-reviewer:s3'
E         'test-role:s2'
E         'test-role:s3'
E         'code-reviewer:s1'
E         'security-reviewer:s1'...
E         
E         ...Full output truncated, use '-vv' to show)

/home/user/wt-2218-wo4/plugins/superheroes/lib/tests/test_unread_waves_c2.py:235: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_unread_waves_c2.py::test_a_later_waves_fold_adds_to_the_first_waves_seat_status_coverage_and_review_record
1 failed, 18 deselected in 0.51s
 plugins/superheroes/lib/decision_kinds.py |   1 +
 plugins/superheroes/lib/round_driver.py   | 173 ++++++++++++++++++++++++++----
 plugins/superheroes/lib/round_phases.py   |  39 ++++++-
 3 files changed, 193 insertions(+), 20 deletions(-)
```

- Restore: the inverse edit. Restored line: `    _record_round(state, "seatStatus", {**prior_status, **seat_status})`.
- Raw green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 18 deselected in 0.55s
 plugins/superheroes/lib/decision_kinds.py |   1 +
 plugins/superheroes/lib/round_driver.py   | 175 ++++++++++++++++++++++++++----
 plugins/superheroes/lib/round_phases.py   |  39 ++++++-
 3 files changed, 194 insertions(+), 21 deletions(-)
```

## E6: carrying the earlier waves' findings

- Guarded element: the `state.pop("_sliceCarry", None)` term of the hand-on in `_after_panel_wave`. Axis: the findings of
  every wave reach the verifiers, each once.
- Neutralization: change `(state.pop("_sliceCarry", None) or []) + this_wave` to
  `(state.pop("_sliceCarry", None) or [])[:0] + this_wave` (the carry is popped and dropped).
- Detector: the bound test, at its findings assertion.
- Raw red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_the_waves_stop_at_the_bound_and_what_is_still_unread_is_recorded_with_every_waves_findings_staged_once _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-73/test_the_waves_stop_at_the_bou0')

    def test_the_waves_stop_at_the_bound_and_what_is_still_unread_is_recorded_with_every_waves_findings_staged_once(tmp_path):
        state = _state(_repo(tmp_path), _three_thousand())
        _wave(state, reads={"test-role:s1": []}, findings={"code-reviewer:s1": [_finding("wave one bug")]})
        assert state["step"] == RD.P_PANEL and state["_sliceWave"] == 2
        _wave(state, reads=NOTHING, findings={"code-reviewer:w2u1": [_finding("wave two bug", line=6)]})
        assert state["step"] == RD.P_PANEL and state["_sliceWave"] == RD.UNREAD_WAVE_BOUND == 3
        assert RP.panel_roster(state, state["config"])[0] == "code-reviewer:w3u1"
        _wave(state, reads=NOTHING, findings={"code-reviewer:w3u1": [_finding("wave three bug", line=7)]})
        assert state["step"] == RD.P_SEAMS
        assert "_sliceWave" not in state and "_sliceCarry" not in state
        assert [i for i in _slice_ids(state) if i.startswith("w4")] == []
        share = state["unreadShare"]
        assert share["unreadLines"] > 0 and share["unreadLines"] <= share["countableLines"]
        assert [p["file"] for p in share["parts"]] == [FIRST]
        decisions = [d for d in state["decisions"] if d["kind"] == "unread-after-waves"]
        assert len(decisions) == 1 and "%d countable line(s) in 1 file(s)" % share["unreadLines"] in decisions[0]["detail"]
        RD._fold(state, state["config"], RD.P_SEAMS, {"findings": []})
>       assert _titles(state) == ["wave one bug", "wave three bug", "wave two bug"]
E       AssertionError: assert ['wave three bug'] == ['wave one bu...wave two bug']
E         
E         At index 0 diff: 'wave three bug' != 'wave one bug'
E         Right contains 2 more items, first extra item: 'wave three bug'
E         Use -v to get more diff

/home/user/wt-2218-wo4/plugins/superheroes/lib/tests/test_unread_waves_c2.py:158: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_unread_waves_c2.py::test_the_waves_stop_at_the_bound_and_what_is_still_unread_is_recorded_with_every_waves_findings_staged_once
1 failed, 18 deselected in 0.54s
 plugins/superheroes/lib/decision_kinds.py |   1 +
 plugins/superheroes/lib/round_driver.py   | 175 ++++++++++++++++++++++++++----
 plugins/superheroes/lib/round_phases.py   |  39 ++++++-
 3 files changed, 194 insertions(+), 21 deletions(-)
```

- Restore: the inverse edit. Restored line: `    _after_panel_findings(state, config, (state.pop("_sliceCarry", None) or []) + this_wave)`.
- Raw green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 18 deselected in 0.51s
 plugins/superheroes/lib/decision_kinds.py |   1 +
 plugins/superheroes/lib/round_driver.py   | 175 ++++++++++++++++++++++++++----
 plugins/superheroes/lib/round_phases.py   |  39 ++++++-
 3 files changed, 194 insertions(+), 21 deletions(-)
```

## Notes

- The E1 red capture opens with a `git diff --stat` taken after the neutralization was applied (176 lines in
  `round_driver.py`); the other captures list the stat after their own step. The post-restore stat of every element equals
  the pre-neutralization 175.
- The restore of each element is by the inverse `Edit`; no `git checkout`, `git restore`, `git reset` or `git stash` was used.
