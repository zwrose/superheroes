# WO-A (#2529) bite-proof — stale seat pins are named in configure's view and the doctor

**Provenance:** claude / sonnet-5.5 (implementer), `plugins/superheroes/lib/seat_map.py`, `plugins/superheroes/lib/configure_view.py`, `plugins/superheroes/lib/repo_doctor.py`. Detector file: `plugins/superheroes/lib/tests/test_stale_seat_pins_2529.py`. Shape and ceilings: `plugins/superheroes/rubric/bite-proof.md`.

Declared guarded-element set (from the order): S1-S5. Each was neutralized by a targeted text edit of the production call site (never the test), the detector file was run red, the neutralization was undone by the inverse text edit (no `git checkout`, `git restore`, `git reset` or `git stash`), and the same file was run green. Every command ran from the worktree root:

```
scripts/pinned-python -B -m pytest plugins/superheroes/lib/tests/test_stale_seat_pins_2529.py -q -p no:cacheprovider
```

Redactions: the `UV_NATIVE_TLS` deprecation warning line that `scripts/pinned-python` prints before every run is dropped; the pytest temp directory `/tmp/claude-0/pytest-of-root/pytest-N` is written `<tmp>`; nothing else was edited. The run is the whole detector file (10 tests), not a single node, because the order names that exact command; the failing node names are in each run's summary. Baseline before any neutralization: `10 passed in 1.51s`.

| ID | Guarded element | Axis | Proving tests (red) |
|---|---|---|---|
| S1 | `configure_view.py` new "Seat pins for seats no roster has" block (`if stale_seats:`) | a stale seat key is named in the view | `test_view_names_a_stale_seat_pin_and_leaves_a_live_pin_line_as_is`, `test_view_names_a_stale_seat_whose_pin_is_broken`, `test_report_only_never_rewrites_core_md` |
| S2 | `configure_view.py` inclusion of rejected keys (`+ list(rejected_seats)`) | a stale seat whose pin is broken is named too | `test_view_names_a_stale_seat_whose_pin_is_broken` |
| S3 | `repo_doctor.py` `staleSeatPins` read (`_stale_seat_pins(root)` at both call sites) | the doctor names a stale seat pin on the unified and the legacy path | `test_doctor_unified_layer_names_a_stale_seat_pin`, `test_doctor_legacy_profile_names_a_stale_seat_pin`, `test_report_only_never_rewrites_core_md` |
| S4 | `repo_doctor.py` hash inclusion (`drift + _stale_entries(stale)` at both call sites) | a stale seat pin joins `signal_hash`, so an acknowledgement covers it | `test_doctor_unified_layer_names_a_stale_seat_pin`, `test_doctor_legacy_profile_names_a_stale_seat_pin` |
| S5 | `seat_map.py` `unknown_pin_seats` alias exclusion (`and k not in LEGACY_SEAT_ALIASES`) | the legacy `test-reviewer` key is a live alias, never stale | `test_unknown_pin_seats_never_names_the_legacy_alias`, `test_doctor_live_pins_only_leave_the_hash_as_it_was`, `test_report_only_never_rewrites_core_md` |

---

## S1 — the view's new block

- **axis:** a stale seat key is named under "Seat pins for seats no roster has"

**neutralization** (`plugins/superheroes/lib/configure_view.py`, line 763):
```diff
--- before (restored text)
        if stale_seats:
+++ neutralized
        if False:
```

**raw red** (exit 1):
```
..FF.....F                                                               [100%]
=================================== FAILURES ===================================
______ test_view_names_a_stale_seat_pin_and_leaves_a_live_pin_line_as_is _______

tmp_path = PosixPath('<tmp>/test_view_names_a_stale_seat_p0')

    def test_view_names_a_stale_seat_pin_and_leaves_a_live_pin_line_as_is(tmp_path):
        lines = _view_lines(tmp_path, {
            "code-reviewer": {"vendor": "codex"},
            "grounding-seat": {"vendor": "codex"},
        })
>       assert VIEW_HEADER in lines
E       AssertionError: assert 'Seat pins for seats no roster has (the panel never seats them; remove them from core.md seatPins):' in ['# superheroes — project calibration', '', 'storage mode: in-repo', 'storage health: ok (1 per-project store)', '', '## Core', ...]

/home/user/wt-2529-a/plugins/superheroes/lib/tests/test_stale_seat_pins_2529.py:177: AssertionError
_______________ test_view_names_a_stale_seat_whose_pin_is_broken ________________

tmp_path = PosixPath('<tmp>/test_view_names_a_stale_seat_w0')

    def test_view_names_a_stale_seat_whose_pin_is_broken(tmp_path):
        lines = _view_lines(tmp_path, {"grounding-seat": "nope"})
        # still under the Rejected block, as it is today
        assert REJECTED_HEADER in lines
        assert "  grounding-seat: pin must be an object with a vendor ⚠" in lines
        # and now named under the new block too
>       assert VIEW_HEADER in lines
E       AssertionError: assert 'Seat pins for seats no roster has (the panel never seats them; remove them from core.md seatPins):' in ['# superheroes — project calibration', '', 'storage mode: in-repo', 'storage health: ok (1 per-project store)', '', '## Core', ...]

/home/user/wt-2529-a/plugins/superheroes/lib/tests/test_stale_seat_pins_2529.py:197: AssertionError
___________________ test_report_only_never_rewrites_core_md ____________________

tmp_path = PosixPath('<tmp>/test_report_only_never_rewrite0')
capsys = <_pytest.capture.CaptureFixture object at 0x7fb827d39a60>

    def test_report_only_never_rewrites_core_md(tmp_path, capsys):
        pins = {"grounding-seat": {"vendor": "codex"}, "test-reviewer": {"vendor": "claude"}}
        view_dir = tmp_path / "viewrepo"
        view_dir.mkdir()
        store = _seed_view(view_dir, pins)
        view_core = view_dir / ".claude" / "superheroes" / "core.md"
        doc_root, env = _make_root(tmp_path)
        doc_core = _write_core(doc_root, pins)
    
        view_before = view_core.read_bytes()
        with open(doc_core, "rb") as fh:
            doc_before = fh.read()
    
        screen = cv.render(str(view_dir), root=store)
        res = _run(_write_layer(tmp_path), doc_root, env, capsys)
    
        # both really did name the stale pin ...
>       assert VIEW_HEADER in screen.splitlines()
E       AssertionError: assert 'Seat pins for seats no roster has (the panel never seats them; remove them from core.md seatPins):' in ['# superheroes — project calibration', '', 'storage mode: in-repo', 'storage health: ok (1 per-project store)', '', '## Core', ...]
E        +  where ['# superheroes — project calibration', '', 'storage mode: in-repo', 'storage health: ok (1 per-project store)', '', '## Core', ...] = <built-in method splitlines of str object at 0x4f818c0>()
E        +    where <built-in method splitlines of str object at 0x4f818c0> = '# superheroes — project calibration\n\nstorage mode: in-repo\nstorage health: ok (1 per-project store)\n\n## Core\nst... or ≥14 days (defaults)\ncoverage: none recorded\nbenched lenses: no sweep history yet\n\n## Pinned patterns\n(none)\n'.splitlines

/home/user/wt-2529-a/plugins/superheroes/lib/tests/test_stale_seat_pins_2529.py:303: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stale_seat_pins_2529.py::test_view_names_a_stale_seat_pin_and_leaves_a_live_pin_line_as_is
FAILED plugins/superheroes/lib/tests/test_stale_seat_pins_2529.py::test_view_names_a_stale_seat_whose_pin_is_broken
FAILED plugins/superheroes/lib/tests/test_stale_seat_pins_2529.py::test_report_only_never_rewrites_core_md
3 failed, 7 passed in 1.58s
```

**restore:** the inverse text edit (`if False:` put back to `if stale_seats:`).

**restore receipt** (`configure_view.py:762-766`, as grep-read back after the restore):
```
762:        stale_seats = seat_map.unknown_pin_seats(list(seat_pins) + list(rejected_seats))
763:        if stale_seats:
766:            for seat in stale_seats:
```

**raw green** (after restore, exit 0):
```
..........                                                               [100%]
10 passed in 1.54s
```

---

## S2 — the view's inclusion of rejected keys

- **axis:** a stale seat whose pin is broken (so it lives in `invalidSeatPins`, not `seatPins`) is named under the new block too

**neutralization** (`plugins/superheroes/lib/configure_view.py`, line 762):
```diff
--- before (restored text)
        stale_seats = seat_map.unknown_pin_seats(list(seat_pins) + list(rejected_seats))
+++ neutralized
        stale_seats = seat_map.unknown_pin_seats(list(seat_pins))
```

**raw red** (exit 1):
```
...F......                                                               [100%]
=================================== FAILURES ===================================
_______________ test_view_names_a_stale_seat_whose_pin_is_broken _______________

tmp_path = PosixPath('<tmp>/test_view_names_a_stale_seat_w0')

    def test_view_names_a_stale_seat_whose_pin_is_broken(tmp_path):
        lines = _view_lines(tmp_path, {"grounding-seat": "nope"})
        # still under the Rejected block, as it is today
        assert REJECTED_HEADER in lines
        assert "  grounding-seat: pin must be an object with a vendor ⚠" in lines
        # and now named under the new block too
>       assert VIEW_HEADER in lines
E       AssertionError: assert 'Seat pins for seats no roster has (the panel never seats them; remove them from core.md seatPins):' in ['# superheroes — project calibration', '', 'storage mode: in-repo', 'storage health: ok (1 per-project store)', '', '## Core', ...]

/home/user/wt-2529-a/plugins/superheroes/lib/tests/test_stale_seat_pins_2529.py:197: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stale_seat_pins_2529.py::test_view_names_a_stale_seat_whose_pin_is_broken
1 failed, 9 passed in 1.57s
```

**restore:** the inverse text edit (`list(seat_pins)` put back to `list(seat_pins) + list(rejected_seats)`).

**restore receipt** (`configure_view.py:762`, grep-read back at the end of the dispatch, after the final regression run; nothing edited that line after S2's restore):
```
762:        stale_seats = seat_map.unknown_pin_seats(list(seat_pins) + list(rejected_seats))
```

**raw green** (after restore, exit 0):
```
..........                                                               [100%]
10 passed in 1.56s
```

---

## S3 — the doctor's `staleSeatPins` read (both call sites)

- **axis:** the doctor names a stale seat pin on the unified-layer path (`_doctor_unified`) and the legacy-profile path (`doctor`)

**neutralization** (`plugins/superheroes/lib/repo_doctor.py`, lines 590 and 638, two edits):
```diff
--- before (restored text)
    stale = _stale_seat_pins(root)            # _doctor_unified, line 590
        stale = _stale_seat_pins(root)        # doctor (legacy), line 638
+++ neutralized
    stale = []
        stale = []
```

**raw red** (exit 1):
```
.....FF..F                                                               [100%]
=================================== FAILURES ===================================
_______________ test_doctor_unified_layer_names_a_stale_seat_pin _______________

tmp_path = PosixPath('<tmp>/test_doctor_unified_layer_name0')
capsys = <_pytest.capture.CaptureFixture object at 0x7fb0703688c0>

    def test_doctor_unified_layer_names_a_stale_seat_pin(tmp_path, capsys):
        root, env = _make_root(tmp_path)
        _write_core(root, {"grounding-seat": {"vendor": "codex"}, "code-reviewer": {"vendor": "codex"}})
        res = _run(_write_layer(tmp_path), root, env, capsys)
>       _assert_stale_named_not_drift(res)

/home/user/wt-2529-a/plugins/superheroes/lib/tests/test_stale_seat_pins_2529.py:220: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

res = {'ok': True, 'readable': True, 'drift': [], 'unchecked': [], ...}

    def _assert_stale_named_not_drift(res):
>       assert res["staleSeatPins"] == ["grounding-seat"]
E       AssertionError: assert [] == ['grounding-seat']
E         
E         Right contains one more item: 'grounding-seat'
E         Use -v to get more diff

/home/user/wt-2529-a/plugins/superheroes/lib/tests/test_stale_seat_pins_2529.py:134: AssertionError
______________ test_doctor_legacy_profile_names_a_stale_seat_pin _______________

tmp_path = PosixPath('<tmp>/test_doctor_legacy_profile_nam0')
capsys = <_pytest.capture.CaptureFixture object at 0x7fb0703693d0>

    def test_doctor_legacy_profile_names_a_stale_seat_pin(tmp_path, capsys):
        root, env = _make_root(tmp_path)
        _write_core(root, {"grounding-seat": {"vendor": "codex"}, "code-reviewer": {"vendor": "codex"}})
        res = _run(_write_profile(tmp_path), root, env, capsys)
>       _assert_stale_named_not_drift(res)

/home/user/wt-2529-a/plugins/superheroes/lib/tests/test_stale_seat_pins_2529.py:233: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

res = {'ok': True, 'readable': True, 'drift': [], 'unchecked': [], ...}

    def _assert_stale_named_not_drift(res):
>       assert res["staleSeatPins"] == ["grounding-seat"]
E       AssertionError: assert [] == ['grounding-seat']
E         
E         Right contains one more item: 'grounding-seat'
E         Use -v to get more diff

/home/user/wt-2529-a/plugins/superheroes/lib/tests/test_stale_seat_pins_2529.py:134: AssertionError
___________________ test_report_only_never_rewrites_core_md ____________________

tmp_path = PosixPath('<tmp>/test_report_only_never_rewrite0')
capsys = <_pytest.capture.CaptureFixture object at 0x7fb07036e840>

    def test_report_only_never_rewrites_core_md(tmp_path, capsys):
        pins = {"grounding-seat": {"vendor": "codex"}, "test-reviewer": {"vendor": "claude"}}
        view_dir = tmp_path / "viewrepo"
        view_dir.mkdir()
        store = _seed_view(view_dir, pins)
        view_core = view_dir / ".claude" / "superheroes" / "core.md"
        doc_root, env = _make_root(tmp_path)
        doc_core = _write_core(doc_root, pins)
    
        view_before = view_core.read_bytes()
        with open(doc_core, "rb") as fh:
            doc_before = fh.read()
    
        screen = cv.render(str(view_dir), root=store)
        res = _run(_write_layer(tmp_path), doc_root, env, capsys)
    
        # both really did name the stale pin ...
        assert VIEW_HEADER in screen.splitlines()
>       assert res["staleSeatPins"] == ["grounding-seat"]
E       AssertionError: assert [] == ['grounding-seat']
E         
E         Right contains one more item: 'grounding-seat'
E         Use -v to get more diff

/home/user/wt-2529-a/plugins/superheroes/lib/tests/test_stale_seat_pins_2529.py:304: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stale_seat_pins_2529.py::test_doctor_unified_layer_names_a_stale_seat_pin
FAILED plugins/superheroes/lib/tests/test_stale_seat_pins_2529.py::test_doctor_legacy_profile_names_a_stale_seat_pin
FAILED plugins/superheroes/lib/tests/test_stale_seat_pins_2529.py::test_report_only_never_rewrites_core_md
3 failed, 7 passed in 1.89s
```

Not covered by this neutralization (stated, not claimed): `test_doctor_stale_pin_fails_soft_on_every_unreadable_shape` calls `_stale_seat_pins` directly, so it stays green here; its own guard is the function body, which this record does not neutralize.

**restore:** the inverse text edits (`stale = []` put back to `stale = _stale_seat_pins(root)` at both sites).

**restore receipt** (`repo_doctor.py`, grep-read back after the S4 restore; the `stale =` lines are unchanged since S3's restore):
```
590:    stale = _stale_seat_pins(root)
638:        stale = _stale_seat_pins(root)
```

**raw green** (after restore, exit 0):
```
..........                                                               [100%]
10 passed in 1.70s
```

---

## S4 — the doctor's hash inclusion (both call sites)

- **axis:** a stale seat pin joins `signal_hash`, so a written `nudge-ack` covers it (and a stale-only root has a non-empty hash)

**neutralization** (`plugins/superheroes/lib/repo_doctor.py`, lines 591 and 639, two edits):
```diff
--- before (restored text)
    signal_hash = _hash_drift(drift + _stale_entries(stale))        # _doctor_unified, line 591
        signal_hash = _hash_drift(drift + _stale_entries(stale))    # doctor (legacy), line 639
+++ neutralized
    signal_hash = _hash_drift(drift)
        signal_hash = _hash_drift(drift)
```

**raw red** (exit 1):
```
.....FF...                                                               [100%]
=================================== FAILURES ===================================
_______________ test_doctor_unified_layer_names_a_stale_seat_pin _______________

tmp_path = PosixPath('<tmp>/test_doctor_unified_layer_name0')
capsys = <_pytest.capture.CaptureFixture object at 0x7f98ddd68710>

    def test_doctor_unified_layer_names_a_stale_seat_pin(tmp_path, capsys):
        root, env = _make_root(tmp_path)
        _write_core(root, {"grounding-seat": {"vendor": "codex"}, "code-reviewer": {"vendor": "codex"}})
        res = _run(_write_layer(tmp_path), root, env, capsys)
>       _assert_stale_named_not_drift(res)

/home/user/wt-2529-a/plugins/superheroes/lib/tests/test_stale_seat_pins_2529.py:220: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

res = {'ok': True, 'readable': True, 'drift': [], 'unchecked': [], ...}

    def _assert_stale_named_not_drift(res):
        assert res["staleSeatPins"] == ["grounding-seat"]
        assert res["message"] == DOCTOR_NOTE
        assert res["drift"] == []
        assert "grounding-seat" not in json.dumps(res["drift"])
>       assert res["signal_hash"] != ""
E       AssertionError: assert '' != ''

/home/user/wt-2529-a/plugins/superheroes/lib/tests/test_stale_seat_pins_2529.py:138: AssertionError
______________ test_doctor_legacy_profile_names_a_stale_seat_pin _______________

tmp_path = PosixPath('<tmp>/test_doctor_legacy_profile_nam0')
capsys = <_pytest.capture.CaptureFixture object at 0x7f98ddd68650>

    def test_doctor_legacy_profile_names_a_stale_seat_pin(tmp_path, capsys):
        root, env = _make_root(tmp_path)
        _write_core(root, {"grounding-seat": {"vendor": "codex"}, "code-reviewer": {"vendor": "codex"}})
        res = _run(_write_profile(tmp_path), root, env, capsys)
>       _assert_stale_named_not_drift(res)

/home/user/wt-2529-a/plugins/superheroes/lib/tests/test_stale_seat_pins_2529.py:233: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

res = {'ok': True, 'readable': True, 'drift': [], 'unchecked': [], ...}

    def _assert_stale_named_not_drift(res):
        assert res["staleSeatPins"] == ["grounding-seat"]
        assert res["message"] == DOCTOR_NOTE
        assert res["drift"] == []
        assert "grounding-seat" not in json.dumps(res["drift"])
>       assert res["signal_hash"] != ""
E       AssertionError: assert '' != ''

/home/user/wt-2529-a/plugins/superheroes/lib/tests/test_stale_seat_pins_2529.py:138: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stale_seat_pins_2529.py::test_doctor_unified_layer_names_a_stale_seat_pin
FAILED plugins/superheroes/lib/tests/test_stale_seat_pins_2529.py::test_doctor_legacy_profile_names_a_stale_seat_pin
2 failed, 8 passed in 1.63s
```

What the red reached (stated, not claimed beyond it): both tests stop at the non-empty `signal_hash` assertion, which sits before their `nudge_acked` assertions, so the red proves the hash inclusion through the `signal_hash != ""` check; the `nudge_acked` assertions were not reached in this red.

**restore:** the inverse text edits (`_hash_drift(drift)` put back to `_hash_drift(drift + _stale_entries(stale))` at both sites).

**restore receipt** (`repo_doctor.py`, grep-read back after the restore):
```
591:    signal_hash = _hash_drift(drift + _stale_entries(stale))
639:        signal_hash = _hash_drift(drift + _stale_entries(stale))
```

**raw green** (after restore, exit 0):
```
..........                                                               [100%]
10 passed in 1.76s
```

---

## S5 — `unknown_pin_seats` alias exclusion

- **axis:** the legacy `test-reviewer` key is a live alias (a key of `LEGACY_SEAT_ALIASES`), never stale

**neutralization** (`plugins/superheroes/lib/seat_map.py`, lines 44-45):
```diff
--- before (restored text)
                       and k not in KNOWN_SEATS
                       and k not in LEGACY_SEAT_ALIASES})
+++ neutralized
                       and k not in KNOWN_SEATS})
```

**raw red** (exit 1):
```
.F.....F.F                                                               [100%]
=================================== FAILURES ===================================
_____________ test_unknown_pin_seats_never_names_the_legacy_alias ______________

    def test_unknown_pin_seats_never_names_the_legacy_alias():
        # `test-reviewer` is a live alias for the test role, never stale
        assert "test-reviewer" in seat_map.LEGACY_SEAT_ALIASES
>       assert seat_map.unknown_pin_seats(["test-reviewer"]) == []
E       AssertionError: assert ['test-reviewer'] == []
E         
E         Left contains one more item: 'test-reviewer'
E         Use -v to get more diff

/home/user/wt-2529-a/plugins/superheroes/lib/tests/test_stale_seat_pins_2529.py:164: AssertionError
_____________ test_doctor_live_pins_only_leave_the_hash_as_it_was ______________

tmp_path = PosixPath('<tmp>/test_doctor_live_pins_only_lea0')
capsys = <_pytest.capture.CaptureFixture object at 0x7f434f6eb200>

    def test_doctor_live_pins_only_leave_the_hash_as_it_was(tmp_path, capsys):
        root, env = _make_root(tmp_path)
        profile = _write_profile(tmp_path)
        # real drift (engine rubric 3 > profile 2), so the hash is non-empty and worth comparing
        _write_core(root, None)
        base = _run(profile, root, env, capsys, rubric=3)
        assert base["drift"] != []
        assert base["signal_hash"] != ""
        _write_core(root, {
            "code-reviewer": {"vendor": "codex"},
            "security-reviewer": {"vendor": "claude"},
            "test-reviewer": {"vendor": "claude"},   # the live legacy alias
        })
        live = _run(profile, root, env, capsys, rubric=3)
>       assert live["staleSeatPins"] == []
E       AssertionError: assert ['test-reviewer'] == []
E         
E         Left contains one more item: 'test-reviewer'
E         Use -v to get more diff

/home/user/wt-2529-a/plugins/superheroes/lib/tests/test_stale_seat_pins_2529.py:256: AssertionError
___________________ test_report_only_never_rewrites_core_md ____________________

tmp_path = PosixPath('<tmp>/test_report_only_never_rewrite0')
capsys = <_pytest.capture.CaptureFixture object at 0x7f434f6d3b00>

    def test_report_only_never_rewrites_core_md(tmp_path, capsys):
        pins = {"grounding-seat": {"vendor": "codex"}, "test-reviewer": {"vendor": "claude"}}
        view_dir = tmp_path / "viewrepo"
        view_dir.mkdir()
        store = _seed_view(view_dir, pins)
        view_core = view_dir / ".claude" / "superheroes" / "core.md"
        doc_root, env = _make_root(tmp_path)
        doc_core = _write_core(doc_root, pins)
    
        view_before = view_core.read_bytes()
        with open(doc_core, "rb") as fh:
            doc_before = fh.read()
    
        screen = cv.render(str(view_dir), root=store)
        res = _run(_write_layer(tmp_path), doc_root, env, capsys)
    
        # both really did name the stale pin ...
        assert VIEW_HEADER in screen.splitlines()
>       assert res["staleSeatPins"] == ["grounding-seat"]
E       AssertionError: assert ['grounding-s...est-reviewer'] == ['grounding-seat']
E         
E         Left contains one more item: 'test-reviewer'
E         Use -v to get more diff

/home/user/wt-2529-a/plugins/superheroes/lib/tests/test_stale_seat_pins_2529.py:304: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stale_seat_pins_2529.py::test_unknown_pin_seats_never_names_the_legacy_alias
FAILED plugins/superheroes/lib/tests/test_stale_seat_pins_2529.py::test_doctor_live_pins_only_leave_the_hash_as_it_was
FAILED plugins/superheroes/lib/tests/test_stale_seat_pins_2529.py::test_report_only_never_rewrites_core_md
3 failed, 7 passed in 1.62s
```

**restore:** the inverse text edit (the `and k not in LEGACY_SEAT_ALIASES})` line put back).

**restore receipt** (`seat_map.py:42-45`, as it stands after the restore):
```
        return sorted({k for k in keys
                       if isinstance(k, str)
                       and k not in KNOWN_SEATS
                       and k not in LEGACY_SEAT_ALIASES})
```

**raw green** (after restore, exit 0):
```
..........                                                               [100%]
10 passed in 1.62s
```

---

## Elements with no proof of their own (stated)

- `engine_pref.safe_config_echo(seat)` around the printed seat name in the view block: the declared set does not include it and no test feeds a control character through it, so no neutralization of it was run. Its protection is unverified.
- The ordering of the new doctor part (after the drift part, before the unchecked part) and the "left out when acknowledged and an unchecked note still has to be shown" rule in `_message`: the detector file drives only roots with no drift and no unchecked note, so neither is neutralized or proven here.
- `unknown_pin_seats`' `KNOWN_SEATS` condition and its non-string-key and fail-soft branches are asserted by `test_unknown_pin_seats_names_only_seats_no_roster_may_name`, but were not in the declared set and were not neutralized.
