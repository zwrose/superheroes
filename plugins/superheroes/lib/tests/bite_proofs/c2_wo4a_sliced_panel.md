# Bite-proof record: C2 WO-4a2, the sliced round-1 panel

Detectors: `plugins/superheroes/lib/tests/test_sliced_panel_c2.py` (and one test in `test_seams_check_c2.py`'s helper).
Every run used: `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-wo -m pytest
plugins/superheroes/lib/tests/test_sliced_panel_c2.py plugins/superheroes/lib/tests/test_seams_check_c2.py
plugins/superheroes/lib/tests/test_review_record_session.py -q -p no:cacheprovider -k <test>`, output piped through `| tail -25` (or
`tail -8` for the greens); every red below fit inside that window, so nothing was cut (each begins at the first line the run printed after
the `UV_NATIVE_TLS` deprecation warning, which is dropped from the quotes below). The tests were unedited between the red and the green.
Each neutralization carried a `NEUTRALIZED-En` marker comment and was undone by the inverse edit. The restore receipt is the restored
line quoted back, plus `git diff --stat` over the neutralized file (an empty stat for `round_phases.py` and `round_driver.py` means the file
is byte-identical to `HEAD` `f903e5d8`, where this work's earlier order committed them; for `review_record_session.py` the stat shows only
the item-2 change itself). Nothing was redacted.

| Entry | Guard | Result |
|---|---|---|
| E1 | `panel_roster` slicing branch | red, then green |
| E2 | per-slice security seating | red, then green |
| E3 | unclear-risk read | red, then green |
| E4 | `seat_lens` in `_seat_map_configured_vendor` | red, then green |
| E5 | storage-key findings path | red, then green |
| E6 | scope line | red, then green |
| E7 | `_bootstrap` plans the slices before the first emission (WO-4a3) | red, then green |
| E8 | `seat_lens` in `review_record_session._unfolded` | red, then green |

## E1: `panel_roster`'s slicing branch (axis: a sliced round 1 seats `<lens>:<id>` seats)

- Neutralization (`round_phases.py`, in `panel_roster`, after `dims = list(panel_dimensions(config))`): inserted `    return dims  # NEUTRALIZED-E1`.
- Test: `test_a_three_thousand_line_change_under_one_folder_seats_a_code_and_a_test_reviewer_per_slice`.
- Raw red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_three_thousand_line_change_under_one_folder_seats_a_code_and_a_test_reviewer_per_slice _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-36/test_a_three_thousand_line_cha0')

    def test_a_three_thousand_line_change_under_one_folder_seats_a_code_and_a_test_reviewer_per_slice(tmp_path):
        # FR-5
        state = _state(_repo(tmp_path), _three_thousand())
        plan = state["slicePlan"]
        assert plan["sliced"] is True and len(plan["slices"]) > 1
        assert all("diff" not in s for s in plan["slices"]), "the state keeps no per-slice diff text"
        roster = RP.panel_roster(state, state["config"])
>       assert "code-reviewer" not in roster and "test-role" not in roster
E       AssertionError: assert ('code-reviewer' not in ['architecture-reviewer', 'code-reviewer', 'security-reviewer', 'test-role', 'premortem-reviewer'])

/home/user/wt-2218-wo4/plugins/superheroes/lib/tests/test_sliced_panel_c2.py:123: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_sliced_panel_c2.py::test_a_three_thousand_line_change_under_one_folder_seats_a_code_and_a_test_reviewer_per_slice
1 failed, 140 deselected in 2.08s
```

- Restore: removed the inserted line (inverse edit). Receipt: `git diff --stat -- plugins/superheroes/lib/round_phases.py` printed nothing.
- Raw green: `.  [100%]` / `1 passed, 140 deselected in 2.37s`.

## E2: per-slice security seating (axis: a slice touching a risk area gets a security seat)

- Neutralization (`round_driver.py`, `_slice_security`): inserted `    return False  # NEUTRALIZED-E2` after the `if "security-reviewer" not in dims: return False` guard.
- Test: `test_a_slice_touching_a_configured_risk_area_gets_a_security_seat_and_one_that_does_not_gets_none`.
- Raw red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_slice_touching_a_configured_risk_area_gets_a_security_seat_and_one_that_does_not_gets_none _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-38/test_a_slice_touching_a_config0')

    def test_a_slice_touching_a_configured_risk_area_gets_a_security_seat_and_one_that_does_not_gets_none(tmp_path):
        state = _state(_repo(tmp_path, RISK_AREAS), _risk_diff())
        slices = state["slicePlan"]["slices"]
        assert len(slices) > 1
        roster = RP.panel_roster(state, state["config"])
        touching = [s for s in slices if any(p["file"] == PAYMENTS for p in s["parts"])]
        clear = [s for s in slices if s not in touching]
        assert touching and clear
        for s in touching:
>           assert s["security"] is True and "security-reviewer:" + s["id"] in roster
E           assert (False is True)

/home/user/wt-2218-wo4/plugins/superheroes/lib/tests/test_sliced_panel_c2.py:206: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_sliced_panel_c2.py::test_a_slice_touching_a_configured_risk_area_gets_a_security_seat_and_one_that_does_not_gets_none
1 failed, 140 deselected in 1.79s
```

- Restore: removed the inserted line. Receipt: `git diff --stat -- plugins/superheroes/lib/round_driver.py` printed nothing, and `git diff -U0 -- plugins/superheroes/lib/round_driver.py | grep -c NEUTRALIZED` printed `0`.
- Raw green: `.  [100%]` / `1 passed, 140 deselected in 1.69s`.

## E3: the unclear-risk read (axis: `not-set` risk areas count as touching)

- Neutralization (`round_driver.py` ~1405): `return found.get("riskAreas") == "not-set" or bool(found.get("touched"))` became `return bool(found.get("touched"))  # NEUTRALIZED-E3`.
- Test: `test_with_risk_areas_not_set_every_slice_gets_a_security_seat`.
- Raw red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_with_risk_areas_not_set_every_slice_gets_a_security_seat _________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-40/test_with_risk_areas_not_set_e0')

    def test_with_risk_areas_not_set_every_slice_gets_a_security_seat(tmp_path):
        state = _state(_repo(tmp_path), _risk_diff())
        roster = RP.panel_roster(state, state["config"])
        assert state["slicePlan"]["slices"]
        for s in state["slicePlan"]["slices"]:
>           assert s["security"] is True and "security-reviewer:" + s["id"] in roster
E           assert (False is True)

/home/user/wt-2218-wo4/plugins/superheroes/lib/tests/test_sliced_panel_c2.py:217: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_sliced_panel_c2.py::test_with_risk_areas_not_set_every_slice_gets_a_security_seat
1 failed, 140 deselected in 1.73s
```

- Restore: the original expression put back. Restored line quoted by `grep -n`: `1405:        return found.get("riskAreas") == "not-set" or bool(found.get("touched"))`; `git diff --stat -- plugins/superheroes/lib/round_driver.py` printed nothing.
- Raw green: `.  [100%]` / `1 passed, 140 deselected in 1.64s`.

## E4: `seat_lens` in `_seat_map_configured_vendor` (axis: a slice seat takes its lens's vendor)

- Neutralization (`round_driver.py` ~3524): `c = seat_map["seats"].get(round_phases.seat_lens(dim))` became `c = seat_map["seats"].get(dim)  # NEUTRALIZED-E4`.
- Test: `test_a_slice_seat_takes_its_lenss_vendor_from_the_seat_map`.
- Raw red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_a_slice_seat_takes_its_lenss_vendor_from_the_seat_map __________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-42/test_a_slice_seat_takes_its_le0')

    def test_a_slice_seat_takes_its_lenss_vendor_from_the_seat_map(tmp_path):
        state = _state(_repo(tmp_path), _three_thousand())
        seat_map = {"seats": {"code-reviewer": {"vendor": "codex", "model": "m1", "engine": "codex"},
                              "test-role": {"vendor": "claude", "model": "m2", "engine": None}}}
        sid = _slice_ids(state)[0]
>       assert RD._seat_map_configured_vendor(seat_map, "code-reviewer:" + sid) == "codex"
E       AssertionError: assert None == 'codex'
E        +  where None = <function _seat_map_configured_vendor at 0x7f8d590aede0>({'seats': {'code-reviewer': {'vendor': 'codex', 'model': 'm1', 'engine': 'codex'}, 'test-role': {'vendor': 'claude', 'model': 'm2', 'engine': None}}}, ('code-reviewer:' + 's1'))
E        +    where <function _seat_map_configured_vendor at 0x7f8d590aede0> = RD._seat_map_configured_vendor

/home/user/wt-2218-wo4/plugins/superheroes/lib/tests/test_sliced_panel_c2.py:303: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_sliced_panel_c2.py::test_a_slice_seat_takes_its_lenss_vendor_from_the_seat_map
1 failed, 140 deselected in 2.10s
```

- Restore: the `seat_lens(dim)` call put back. `git diff --stat -- plugins/superheroes/lib/round_driver.py` printed nothing.
- Raw green: `.  [100%]` / `1 passed, 140 deselected in 1.88s`.

## E5: the storage-key findings path (axis: two slices of one lens never share a findings file)

- Neutralization (`round_driver.py`, `_panel_findings_stem`): the slice branch `return round_records.storage_key(seat_key, occurrence)` became `return AGENT_SUFFIX.get(round_phases.seat_lens(seat_key), seat_key)  # NEUTRALIZED-E5`.
- Test: `test_two_code_reviewer_slice_seats_write_findings_files_of_their_own`.
- Raw red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_two_code_reviewer_slice_seats_write_findings_files_of_their_own _____

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-44/test_two_code_reviewer_slice_s0')

    def test_two_code_reviewer_slice_seats_write_findings_files_of_their_own(tmp_path):
        state = _state(_repo(tmp_path), _three_thousand())
        sdir = _session_dir(tmp_path)
        ids = _slice_ids(state)
        assert len(ids) > 1
        paths = [_placeholders(state, sdir, "code-reviewer:" + sid)["FINDINGS_OUTPUT_PATH"] for sid in ids]
>       assert len(set(paths)) == len(paths)
E       AssertionError: assert 1 == 3
E        +  where 1 = len({'/tmp/claude-0/pytest-of-root/pytest-44/test_two_code_reviewer_slice_s0/session/round-1/findings-code.json'})
E        +    where {'/tmp/claude-0/pytest-of-root/pytest-44/test_two_code_reviewer_slice_s0/session/round-1/findings-code.json'} = set(['/tmp/claude-0/pytest-of-root/pytest-44/test_two_code_reviewer_slice_s0/session/round-1/findings-code.json', '/tmp/cl...ode.json', '/tmp/claude-0/pytest-of-root/pytest-44/test_two_code_reviewer_slice_s0/session/round-1/findings-code.json'])
E        +  and   3 = len(['/tmp/claude-0/pytest-of-root/pytest-44/test_two_code_reviewer_slice_s0/session/round-1/findings-code.json', '/tmp/cl...ode.json', '/tmp/claude-0/pytest-of-root/pytest-44/test_two_code_reviewer_slice_s0/session/round-1/findings-code.json'])

/home/user/wt-2218-wo4/plugins/superheroes/lib/tests/test_sliced_panel_c2.py:271: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_sliced_panel_c2.py::test_two_code_reviewer_slice_seats_write_findings_files_of_their_own
1 failed, 140 deselected in 2.01s
```

(The `...` inside the `set([...])` repr is pytest's own elision.)

- Restore: the `return round_records.storage_key(seat_key, occurrence)` line put back. `git diff --stat -- plugins/superheroes/lib/round_driver.py` printed nothing.
- Raw green: `.  [100%]` / `1 passed, 140 deselected in 2.01s`.

## E6: the scope line (axis: a slice seat's order names its parts)

- Neutralization (`round_driver.py` ~13697): `"SLICE_SCOPE_LINE": scope_line,` became `"SLICE_SCOPE_LINE": "",  # NEUTRALIZED-E6`.
- Test: `test_a_rendered_slice_seat_order_carries_the_scope_line_and_a_whole_change_seat_order_does_not`.
- Raw red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_rendered_slice_seat_order_carries_the_scope_line_and_a_whole_change_seat_order_does_not _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-46/test_a_rendered_slice_seat_ord0')

    def test_a_rendered_slice_seat_order_carries_the_scope_line_and_a_whole_change_seat_order_does_not(tmp_path):
        state = _state(_repo(tmp_path), _risk_diff())
        sdir = _session_dir(tmp_path)
        row = {"vendor": "claude", "model": None, "engine": None}
        sid = _slice_ids(state)[0]
        texts = {}
        for seat in ("code-reviewer:" + sid, "architecture-reviewer"):
            context, _paths = RD._build_order_render_context(sdir, state, 1, RD.P_PANEL, 0, seat, 0, {}, row)
            texts[seat], reason = RO.render_order(RD.P_PANEL, seat, context)
            assert reason is None, reason
>       assert "Your slice: %s. Review only these parts of the change" % sid in texts["code-reviewer:" + sid]
E       AssertionError: assert ('Your slice: %s. Review only these parts of the change' % 's1') in 'You are reviewing pr for repo unknown, target unknown.\nReview session mode was not set in session metadata or driver..._a_rendered_slice_seat_ord0/session/round-1/landing/dispatch-panel/code-reviewer-s1-271e703e93275457.a0.payload.json\n'

/home/user/wt-2218-wo4/plugins/superheroes/lib/tests/test_sliced_panel_c2.py:261: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_sliced_panel_c2.py::test_a_rendered_slice_seat_order_carries_the_scope_line_and_a_whole_change_seat_order_does_not
1 failed, 140 deselected in 2.17s
```

(The `...` inside the rendered order text is pytest's own elision.)

- Restore: `"SLICE_SCOPE_LINE": scope_line,` put back. `git diff --stat -- plugins/superheroes/lib/round_driver.py` printed nothing.
- Raw green: `.  [100%]` / `1 passed, 140 deselected in 2.01s`.

## E7: `_bootstrap` plans the slices before the first emission (WO-4a3; axis: a slice seat's emission and its anchor check agree)

No library fix was made: the `manifest-anchor-mismatch` was a test-helper defect, and the fix is in `test_round_driver_integration._bootstrap`.
`new_state` plans slices before the first emission (`round_driver.py:1391`), so a real session never sees it. The helper's old order ran
`cmd_next` (which planned no slices and emitted plain-roster orders) and only then wrote a `slicePlan` into saved state. The fix runs the one
real `cmd_next` with `round_driver._plan_slices` swapped for `_fixture_slice_plan` (`mock.patch.object`), so emission, anchor and roster read
the same plan. `sliced` now defaults to `False`; a test opts in with `sliced=True`.

- Guarded element: the `sliced=True` branch of `_bootstrap` in `test_round_driver_integration.py`. Axis: the plan is in state before the first panel emission.
- Neutralization: the `if sliced:` / `with mock.patch.object(...)` / `else:` block was replaced by the old order, each line tagged `# NEUTRALIZED-E7`:
  `out = round_driver.cmd_next(session_dir, _cfg(**cfg_over))`, then `assert out["ok"], out`, then
  `if sliced: state = _state(session_dir); state["slicePlan"] = copy.deepcopy(SLICE_PLAN); round_driver.save_state(session_dir, state)`.
- Test: `test_every_adapter_phase_folds_and_the_round_reaches_a_terminal_receipt` (the one test that passes `sliced=True` and drives the real
  adapter), run alone with `-k`, output through `| tail -30`. The tail began at the `_drive_one_phase` frame, so the head of the failure
  report (the test body frame) is not quoted; the decisive assertion line is.
- Raw red (the `tail -30` window only; the lines of the report above it, including the test-body frame, are cut):

```
session_dir = '/tmp/claude-0/pytest-of-root/pytest-58/test_every_adapter_phase_folds0/s'
gitdir = '/tmp/claude-0/pytest-of-root/pytest-58/test_every_adapter_phase_folds0/s-gitdir'
panel_findings = [{'file': 'src/f00.py', 'line': 2, 'title': 'missing bounds guard', 'severity': 'Important', ...}, {'_seat': 'test-role', 'file': 'src/f01.py', 'line': 2, 'title': 'a retried write is applied twice', ...}]
head_diff_path = '/tmp/claude-0/pytest-of-root/pytest-58/test_every_adapter_phase_folds0/s-head.diff'

    def _drive_one_phase(session_dir, gitdir, panel_findings, head_diff_path):
        """Land + record every roster slot of the pending phase, then `advance`. -> (phase, out)."""
        _assert_adapters_are_real()
        state = _state(session_dir)
        pend = state["pending"]
        phase = pend["phase"]
        assert phase in round_adapters.ADAPTER_PHASES, (
            "phase %r is not an adapter phase — this harness drives dispatch phases only" % phase)
        roster, reason = round_adapters.roster_for(phase, state, state.get("config") or {})
        assert reason is None, (phase, reason)
        slots = _slots_of(roster)
        _write_dispatch_manifest(session_dir, pend, slots, _auditor_vendor_for(state))
        for seat, occurrence in slots:
            payload = _payload_for(session_dir, state, pend, seat, panel_findings, head_diff_path)
            _land(session_dir, state, pend, seat, payload, occurrence=occurrence)
            out = _record(session_dir, seat, occurrence=occurrence)
>           assert out["ok"], (phase, seat, occurrence, out)
E           AssertionError: ('dispatch-panel', 'code-reviewer:s1', 0, {'ok': False, 'reason': 'manifest-anchor-mismatch', 'seat': 'code-reviewer:s1', 'detail': None})
E           assert False

/home/user/wt-2218-wo4/plugins/superheroes/lib/tests/test_round_driver_integration.py:483: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_round_driver_integration.py::test_every_adapter_phase_folds_and_the_round_reaches_a_terminal_receipt
1 failed, 18 deselected in 1.75s
```

(The `...` inside the `panel_findings` repr is pytest's own elision. Nothing was redacted.)

- Restore: the `with mock.patch.object(round_driver, "_plan_slices", _fixture_slice_plan):` form put back by the inverse edit. Restore receipt:
  `grep -c NEUTRALIZED` over the file printed `0`, and `grep -n "if sliced:" -B1 -A5` printed
  `549:    if sliced:` / `550:        with mock.patch.object(round_driver, "_plan_slices", _fixture_slice_plan):` /
  `551:            out = round_driver.cmd_next(session_dir, _cfg(**cfg_over))` / `552:    else:` / `553:        out = round_driver.cmd_next(session_dir, _cfg(**cfg_over))` /
  `554:    assert out["ok"], out`.
- Raw green: `.  [100%]` / `1 passed, 18 deselected in 4.62s`.

Observed before any change (a scratch reproduction of the harness; `_anchor_check` compares `envelope["orderSha256"]` with `anchor["orders"][storage_key(seat, occurrence)]`):
roster `['architecture-reviewer', 'premortem-reviewer', 'code-reviewer:s1', 'test-role:s1', 'code-reviewer:s2', 'test-role:s2']`;
anchor orders keys `['architecture-reviewer-b784c838315fcad8', 'code-reviewer-e08ba693bb6ad36a', 'premortem-reviewer-8604769b846a4c86', 'security-reviewer-8a78bab66f6a0d49', 'test-role-b37ea5b042a8102d']`.
No key for `code-reviewer:s1`, so the test's `_anchor_hashes` handed back `not-emitted`, and `_anchor_check` refused (`want_order` was `None`).

## E8: `seat_lens` in `review_record_session._unfolded` (axis: a `test-role:<id>` seat is the test role there)

- Neutralization (`review_record_session.py` ~826): `round_phases.seat_lens(seat) == break_it.ROLE` became `seat == break_it.ROLE`.
- Test (new): `test_a_passed_break_it_proposal_from_a_test_role_slice_seat_is_settled_like_the_whole_change_seats` (three cases; only `slice-test-role` goes red).
- Raw red:

```
.F.                                                                      [100%]
=================================== FAILURES ===================================
_ test_a_passed_break_it_proposal_from_a_test_role_slice_seat_is_settled_like_the_whole_change_seats[slice-test-role] _

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7fda0744f020>
seat = 'test-role:s1', listed = False

    @pytest.mark.parametrize("seat, listed", [("test-role", False), ("test-role:s1", False), ("code-reviewer:s1", True)],
                             ids=["whole-change-test-role", "slice-test-role", "slice-code-reviewer"])
    def test_a_passed_break_it_proposal_from_a_test_role_slice_seat_is_settled_like_the_whole_change_seats(monkeypatch, seat,
                                                                                                        listed):
        import review_record_session as rs
        proposal = {"title": "boundary breaks", "file": "src/a.py", "line": 1, "taxonomy": "break-it-test",
                    "severity": "Important", "consequence": "a bad input gets through"}
        monkeypatch.setattr(rs, "_raised_reports", lambda *a, **k: [(RP.P_PANEL, 1, seat, [proposal])])
        rounds = {"1": {"breakItRuns": [{"outcome": "passed", "title": "boundary breaks", "file": "src/a.py"}]}}
        rows = rs._unfolded("unused", [], rounds, [])
>       assert [r["reviewer"] for r in rows] == ([seat] if listed else [])
E       AssertionError: assert ['test-role:s1'] == []
E         
E         Left contains one more item: 'test-role:s1'
E         Use -v to get more diff

/home/user/wt-2218-wo4/plugins/superheroes/lib/tests/test_sliced_panel_c2.py:382: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_sliced_panel_c2.py::test_a_passed_break_it_proposal_from_a_test_role_slice_seat_is_settled_like_the_whole_change_seats[slice-test-role]
1 failed, 2 passed, 138 deselected in 1.81s
```

- Restore: the `round_phases.seat_lens(seat) == break_it.ROLE` form put back. `git diff --stat -- plugins/superheroes/lib/review_record_session.py` printed
  ` plugins/superheroes/lib/review_record_session.py | 2 +-` / ` 1 file changed, 1 insertion(+), 1 deletion(-)`, and `git diff -U0` showed the one changed line:
  `-            settled = phase == round_phases.P_PANEL and seat == break_it.ROLE and break_it.is_break_it(f) \`
  `+            settled = phase == round_phases.P_PANEL and round_phases.seat_lens(seat) == break_it.ROLE and break_it.is_break_it(f) \`
- Raw green: `...  [100%]` / `3 passed, 138 deselected in 1.81s`.
