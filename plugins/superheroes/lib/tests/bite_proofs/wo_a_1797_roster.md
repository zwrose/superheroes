# WO-A (#1797) bite-proof — the full-lane roster follows the lane call

**Provenance:** claude / sonnet (implementer), `plugins/superheroes/lib/seat_map.py`, `plugins/superheroes/lib/review_record.py`.

Declared guarded-element set (from the order): G1-G7. Each was neutralized by an exact text swap in production code only, the proving node was run red, the neutralization was undone by the inverse text swap, and the same node was run green. Temp paths are the only redaction (`<tmp>` for the pytest temp root, `<repo>` for the worktree root); nothing else was edited. All commands ran from `<repo>`.

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| G1 | `roster_for` adds the specialists on a non-None floor (`seat_map.py` `roster_for`) | a basis whose floor is not None gets the security and premortem seats | `test_roster_for_full_floor_adds_the_specialists` |
| G2 | `roster_for` fail-closed branch (`seat_map.py` `roster_for`) | a basis that is missing, not a dict, or has no `floor` key gets the full risky roster | `test_roster_for_fails_closed_on_a_basis_it_cannot_read` |
| G3 | compose's fail-closed `unavailable` on a missing base (`seat_map.py` `_lane_basis`) | a compose with no `--base-ref` composes the risky roster, never a shrunk one | `test_compose_without_a_base_ref_composes_the_risky_roster` |
| G4 | `MAKER_EXCLUDED_SEATS` over `KNOWN_SEATS` (`seat_map.py`, constant) | the maker's family is barred from every known seat, architecture included, even when it is composed through an explicit roster | `test_an_architecture_seat_composed_through_an_explicit_roster_cannot_be_pinned_to_a_maker` |
| G5 | `required_critical_families` scaling (`seat_map.py`) | the critical-diversity bar is the roster's, not a fixed two; a one-critical-seat roster is not held to two families | `test_required_critical_families_scales_with_the_critical_seats_the_roster_seats` and `test_a_valid_no_floor_panel_has_no_critical_diversity_degradation_or_violation` |
| G6 | compose merging core.md `seatPins` (`seat_map.py` `main`, compose branch) | compose reads `enginePreferences.seatPins` from core.md itself, so a pin binds a seat with no `--pins` given | `test_core_md_seat_pins_bind_a_base_seat_and_a_specialist_with_no_pins_flag` |
| G7 | `_move_up_blocker` uses the composed roster (`review_record.py`) | the move-up check requires the roster the lane basis calls for, not the full panel | `test_move_up_holds_a_no_floor_basis_to_the_three_seat_roster` |

## Disclosures

- G5 has two proving nodes (the two axis comments in the order's tests); they were run together in one command for the red and the green half, and both went red under the one neutralization.
- The proving nodes of G1, G3 and G6 build a throwaway git repo; they commit with `commit.gpgsign=false` set by the test helper, so they ran green here. No node used for a proof is the deselected `test_lane_marker_is_none_when_the_marker_path_cannot_be_resolved`.
- Not separately neutralized, so listed as unproven: the `verify()` `roster-missing-required` loop, the `effective_roster` fall-back to `PANEL_ROSTER` in `build()`/`verify()`/`classify_violations()`, the `same_family_degradations` scan over the map's own roster, the `laneBasis` receipt shape, and the other `_lane_basis` fail-closed edges (empty or falsy `--head-sha`, git failure, timeout, undecodable output). Each is exercised green by its own test in `test_seat_map.py`, with no red shown here.
- G7 was neutralized to `PANEL_ROSTER` (the "no basis" requirement), which is exactly what the order's tests for a risky basis and for no basis expect; only the no-floor node can go red under it, and it did.
- Restore receipts: the neutralized line is quoted back as it stands in the file after the inverse edit, and the sha256 of `seat_map.py` and `review_record.py` after each restore is compared with the value taken before the first neutralization.

Baseline sha256, taken before G1 (the same two lines came back after every restore):
```
6abf5b4038f36b353c940748c27d05ce3d2177edd29aa32278edbb5408f5e853  plugins/superheroes/lib/seat_map.py
d6d8454a49d8e7fe8920443e8dd8300869bdcf559c0edc26b48722f8acf70fb1  plugins/superheroes/lib/review_record.py
```

---

## G1 — `roster_for` adds the specialists on a non-None floor (`seat_map.py` `roster_for`)

- **axis:** a basis whose floor is not None gets the security and premortem seats

**neutralization** (`plugins/superheroes/lib/seat_map.py`):
```diff
--- before (restored text)
    if isinstance(lane_basis, dict) and "floor" in lane_basis and lane_basis["floor"] is None:
+++ neutralized
    if isinstance(lane_basis, dict) and "floor" in lane_basis:
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_seat_map.py::test_roster_for_full_floor_adds_the_specialists -q -p no:cacheprovider
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______________ test_roster_for_full_floor_adds_the_specialists ________________

tmp_path = PosixPath('<tmp>/pytest-of-root/pytest-44/test_roster_for_full_floor_add0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7feb5a3b95b0>

    def test_roster_for_full_floor_adds_the_specialists(tmp_path, monkeypatch):
        # axis: a basis whose floor is not None gets the security and premortem seats — see bite-proof record wo_a_1797_roster
        for name, basis in _bases(tmp_path, monkeypatch).items():
            assert basis["floor"] == "full", name
>           assert SM.roster_for(basis) == RISKY_ROSTER, name
E           AssertionError: touches-a-risk-area
E           assert ('code-review...ounding-seat') == ('code-review...ounding-seat')
E             
E             At index 1 diff: 'test-role' != 'security-reviewer'
E             Right contains 2 more items, first extra item: 'premortem-reviewer'
E             Use -v to get more diff

<repo>/plugins/superheroes/lib/tests/test_seat_map.py:4353: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_roster_for_full_floor_adds_the_specialists
1 failed in 0.65s
red exit: 1
```

**restore:** the inverse text swap of the neutralization above (the "before" text put back; no `git checkout`, `git restore`, `git reset` or `git stash`).

**restore receipt** (restored line as it stands in the file, `seat_map.py:75`):
```
    if isinstance(lane_basis, dict) and "floor" in lane_basis and lane_basis["floor"] is None:
```
sha256 after the restore (identical to the baseline):
```
6abf5b4038f36b353c940748c27d05ce3d2177edd29aa32278edbb5408f5e853  plugins/superheroes/lib/seat_map.py
d6d8454a49d8e7fe8920443e8dd8300869bdcf559c0edc26b48722f8acf70fb1  plugins/superheroes/lib/review_record.py
```

**raw green** (after restore):
```
.                                                                        [100%]
1 passed in 1.37s
green exit: 0
```

---

## G2 — `roster_for` fail-closed branch (`seat_map.py` `roster_for`)

- **axis:** a basis that is missing, not a dict, or has no `floor` key gets the full risky roster

**neutralization** (`plugins/superheroes/lib/seat_map.py`):
```diff
--- before (restored text)
    if isinstance(lane_basis, dict) and "floor" in lane_basis and lane_basis["floor"] is None:
+++ neutralized
    if isinstance(lane_basis, dict) and lane_basis.get("floor") is None:
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_seat_map.py::test_roster_for_fails_closed_on_a_basis_it_cannot_read -q -p no:cacheprovider
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_roster_for_fails_closed_on_a_basis_it_cannot_read ____________

    def test_roster_for_fails_closed_on_a_basis_it_cannot_read():
        # axis: a basis that is missing, not a dict, or has no floor key gets the full risky roster — see bite-proof record wo_a_1797_roster
        for basis in (None, "full", [], 7, {}, {"lane": "full"}, {"floor": "full"}, {"floor": ""}, {"floor": "none"}):
>           assert SM.roster_for(basis) == RISKY_ROSTER, basis
E           AssertionError: {}
E           assert ('code-review...ounding-seat') == ('code-review...ounding-seat')
E             
E             At index 1 diff: 'test-role' != 'security-reviewer'
E             Right contains 2 more items, first extra item: 'premortem-reviewer'
E             Use -v to get more diff

<repo>/plugins/superheroes/lib/tests/test_seat_map.py:4367: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_roster_for_fails_closed_on_a_basis_it_cannot_read
1 failed in 0.31s
red exit: 1
```

**restore:** the inverse text swap of the neutralization above (no `git checkout`, `git restore`, `git reset` or `git stash`).

**restore receipt** (restored line, `seat_map.py:75`):
```
    if isinstance(lane_basis, dict) and "floor" in lane_basis and lane_basis["floor"] is None:
```
sha256 after the restore (identical to the baseline):
```
6abf5b4038f36b353c940748c27d05ce3d2177edd29aa32278edbb5408f5e853  plugins/superheroes/lib/seat_map.py
d6d8454a49d8e7fe8920443e8dd8300869bdcf559c0edc26b48722f8acf70fb1  plugins/superheroes/lib/review_record.py
```

**raw green** (after restore):
```
.                                                                        [100%]
1 passed in 0.15s
green exit: 0
```

---

## G3 — compose's fail-closed `unavailable` on a missing base (`seat_map.py` `_lane_basis`)

- **axis:** a compose with no `--base-ref` composes the risky roster, never a shrunk one

**neutralization** (`plugins/superheroes/lib/seat_map.py`):
```diff
--- before (restored text)
        return closed("no --base-ref was given")
+++ neutralized
        return dict(closed("no --base-ref was given"), floor=None)
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_seat_map.py::test_compose_without_a_base_ref_composes_the_risky_roster -q -p no:cacheprovider
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_compose_without_a_base_ref_composes_the_risky_roster ___________

tmp_path = PosixPath('<tmp>/pytest-of-root/pytest-48/test_compose_without_a_base_re0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7efe268fd5b0>
capsys = <_pytest.capture.CaptureFixture object at 0x7efe269d16a0>

    def test_compose_without_a_base_ref_composes_the_risky_roster(tmp_path, monkeypatch, capsys):
        # axis: compose's fail-closed lane basis on a missing base ref — see bite-proof record wo_a_1797_roster
        repo, _base, _head = _project(tmp_path, monkeypatch, areas=[_PAYMENTS])
        _parent, docs_head = _docs_commit(repo)
        receipt = _compose(capsys, repo, head=docs_head)
>       assert tuple(receipt["roster"]) == RISKY_ROSTER
E       AssertionError: assert ('code-review...ounding-seat') == ('code-review...ounding-seat')
E         
E         At index 1 diff: 'test-role' != 'security-reviewer'
E         Right contains 2 more items, first extra item: 'premortem-reviewer'
E         Use -v to get more diff

<repo>/plugins/superheroes/lib/tests/test_seat_map.py:4410: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_compose_without_a_base_ref_composes_the_risky_roster
1 failed in 0.44s
red exit: 1
```

**restore:** the inverse text swap of the neutralization above (no `git checkout`, `git restore`, `git reset` or `git stash`).

**restore receipt** (restored line, `seat_map.py:1467`):
```
        return closed("no --base-ref was given")
```
sha256 after the restore (identical to the baseline):
```
6abf5b4038f36b353c940748c27d05ce3d2177edd29aa32278edbb5408f5e853  plugins/superheroes/lib/seat_map.py
d6d8454a49d8e7fe8920443e8dd8300869bdcf559c0edc26b48722f8acf70fb1  plugins/superheroes/lib/review_record.py
```

**raw green** (after restore):
```
.                                                                        [100%]
1 passed in 0.30s
green exit: 0
```

---

## G4 — `MAKER_EXCLUDED_SEATS` over `KNOWN_SEATS` (`seat_map.py`, constant)

- **axis:** the maker's family is barred from every known seat, architecture included, even when it is composed through an explicit roster

**neutralization** (`plugins/superheroes/lib/seat_map.py`):
```diff
--- before (restored text)
MAKER_EXCLUDED_SEATS = frozenset(KNOWN_SEATS)
+++ neutralized
MAKER_EXCLUDED_SEATS = frozenset(PANEL_ROSTER)
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_seat_map.py::test_an_architecture_seat_composed_through_an_explicit_roster_cannot_be_pinned_to_a_maker -q -p no:cacheprovider
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_an_architecture_seat_composed_through_an_explicit_roster_cannot_be_pinned_to_a_maker _

    def test_an_architecture_seat_composed_through_an_explicit_roster_cannot_be_pinned_to_a_maker():
        # axis: MAKER_EXCLUDED_SEATS covers every known seat, architecture included — see bite-proof record wo_a_1797_roster
        pins = {"architecture-reviewer": {"vendor": "claude"}}
        m = SM.build(SM.KNOWN_SEATS, THREE_VENDORS, "anthropic", "openai", 0, pins=pins)
>       assert m["seats"]["architecture-reviewer"]["source"] == "unfilled"
E       AssertionError: assert 'pinned' == 'unfilled'
E         
E         - unfilled
E         + pinned

<repo>/plugins/superheroes/lib/tests/test_seat_map.py:4566: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_an_architecture_seat_composed_through_an_explicit_roster_cannot_be_pinned_to_a_maker
1 failed in 0.16s
red exit: 1
```

**restore:** the inverse text swap of the neutralization above (no `git checkout`, `git restore`, `git reset` or `git stash`).

**restore receipt** (restored line, `seat_map.py:49`):
```
MAKER_EXCLUDED_SEATS = frozenset(KNOWN_SEATS)
```
sha256 after the restore (identical to the baseline):
```
6abf5b4038f36b353c940748c27d05ce3d2177edd29aa32278edbb5408f5e853  plugins/superheroes/lib/seat_map.py
d6d8454a49d8e7fe8920443e8dd8300869bdcf559c0edc26b48722f8acf70fb1  plugins/superheroes/lib/review_record.py
```

**raw green** (after restore):
```
.                                                                        [100%]
1 passed in 0.12s
green exit: 0
```

---

## G5 — `required_critical_families` scaling (`seat_map.py`)

- **axis:** the critical-diversity bar is the roster's, not a fixed two; a one-critical-seat roster is not held to two families

**neutralization** (`plugins/superheroes/lib/seat_map.py`):
```diff
--- before (restored text)
    return min(MIN_CRITICAL_FAMILIES, len(CRITICAL_SEATS & set(roster)))
+++ neutralized
    return MIN_CRITICAL_FAMILIES
```

**command** (both proving nodes, one invocation):
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_seat_map.py::test_required_critical_families_scales_with_the_critical_seats_the_roster_seats plugins/superheroes/lib/tests/test_seat_map.py::test_a_valid_no_floor_panel_has_no_critical_diversity_degradation_or_violation -q -p no:cacheprovider
```

**raw red** (exit 1):
```
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_required_critical_families_scales_with_the_critical_seats_the_roster_seats _

    def test_required_critical_families_scales_with_the_critical_seats_the_roster_seats():
        # axis: the critical-diversity bar is the roster's, not a fixed two — see bite-proof record wo_a_1797_roster
        assert SM.required_critical_families(SM.PANEL_ROSTER) == 2
        assert SM.required_critical_families(SM.KNOWN_SEATS) == 2
>       assert SM.required_critical_families(NO_FLOOR_ROSTER) == 1
E       AssertionError: assert 2 == 1
E        +  where 2 = <function required_critical_families at 0x7f444bfb4680>(('code-reviewer', 'test-role', 'grounding-seat'))
E        +    where <function required_critical_families at 0x7f444bfb4680> = SM.required_critical_families

<repo>/plugins/superheroes/lib/tests/test_seat_map.py:4537: AssertionError
_ test_a_valid_no_floor_panel_has_no_critical_diversity_degradation_or_violation _

    def test_a_valid_no_floor_panel_has_no_critical_diversity_degradation_or_violation():
        # axis: a one-critical-seat roster is not held to two families — see bite-proof record wo_a_1797_roster
        for live in (["claude"], ["claude", "codex"], THREE_VENDORS):
            m = SM.build(NO_FLOOR_ROSTER, live, "xai", "anthropic", 0)
>           assert not any(d["constraint"] == "critical-diversity" for d in m["degradations"]), live
E           AssertionError: ['claude']
E           assert not True
E            +  where True = any(<generator object test_a_valid_no_floor_panel_has_no_critical_diversity_degradation_or_violation.<locals>.<genexpr> at 0x7f444be5fac0>)

<repo>/plugins/superheroes/lib/tests/test_seat_map.py:4544: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_required_critical_families_scales_with_the_critical_seats_the_roster_seats
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_a_valid_no_floor_panel_has_no_critical_diversity_degradation_or_violation
2 failed in 0.20s
red exit: 1
```

**restore:** the inverse text swap of the neutralization above (no `git checkout`, `git restore`, `git reset` or `git stash`).

**restore receipt** (restored line, `seat_map.py:91`):
```
    return min(MIN_CRITICAL_FAMILIES, len(CRITICAL_SEATS & set(roster)))
```
sha256 after the restore (identical to the baseline):
```
6abf5b4038f36b353c940748c27d05ce3d2177edd29aa32278edbb5408f5e853  plugins/superheroes/lib/seat_map.py
d6d8454a49d8e7fe8920443e8dd8300869bdcf559c0edc26b48722f8acf70fb1  plugins/superheroes/lib/review_record.py
```

**raw green** (after restore):
```
..                                                                       [100%]
2 passed in 0.10s
green exit: 0
```

---

## G6 — compose merging core.md `seatPins` (`seat_map.py` `main`, compose branch)

- **axis:** compose reads `enginePreferences.seatPins` from core.md itself, so a pin binds a seat with no `--pins` given

**neutralization** (`plugins/superheroes/lib/seat_map.py`):
```diff
--- before (restored text)
        core_pins = prefs.get("seatPins")
+++ neutralized
        core_pins = None
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_seat_map.py::test_core_md_seat_pins_bind_a_base_seat_and_a_specialist_with_no_pins_flag -q -p no:cacheprovider
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
__ test_core_md_seat_pins_bind_a_base_seat_and_a_specialist_with_no_pins_flag __

tmp_path = PosixPath('<tmp>/pytest-of-root/pytest-54/test_core_md_seat_pins_bind_a_0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f8f62e295b0>
capsys = <_pytest.capture.CaptureFixture object at 0x7f8f62efd7f0>

    def test_core_md_seat_pins_bind_a_base_seat_and_a_specialist_with_no_pins_flag(tmp_path, monkeypatch, capsys):
        # axis: compose reads enginePreferences.seatPins from core.md itself — see bite-proof record wo_a_1797_roster
        prefs = {"seatPins": {"code-reviewer": {"vendor": "claude"}, "security-reviewer": {"vendor": "claude"}}}
        repo, _base, _head = _project(tmp_path, monkeypatch, prefs=prefs)
        receipt = _compose(capsys, repo)
        for seat in ("code-reviewer", "security-reviewer"):
>           assert receipt["seats"][seat]["source"] == "pinned", seat
E           AssertionError: code-reviewer
E           assert 'rotated' == 'pinned'
E             
E             - pinned
E             + rotated

<repo>/plugins/superheroes/lib/tests/test_seat_map.py:4462: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_core_md_seat_pins_bind_a_base_seat_and_a_specialist_with_no_pins_flag
1 failed in 0.29s
red exit: 1
```

**restore:** the inverse text swap of the neutralization above (no `git checkout`, `git restore`, `git reset` or `git stash`).

**restore receipt** (restored line, `seat_map.py:1586`):
```
        core_pins = prefs.get("seatPins")
```
sha256 after the restore (identical to the baseline):
```
6abf5b4038f36b353c940748c27d05ce3d2177edd29aa32278edbb5408f5e853  plugins/superheroes/lib/seat_map.py
d6d8454a49d8e7fe8920443e8dd8300869bdcf559c0edc26b48722f8acf70fb1  plugins/superheroes/lib/review_record.py
```

**raw green** (after restore):
```
.                                                                        [100%]
1 passed in 0.25s
green exit: 0
```

---

## G7 — `_move_up_blocker` uses the composed roster (`review_record.py`)

- **axis:** the move-up check requires the roster the lane basis calls for, not the full panel

**neutralization** (`plugins/superheroes/lib/review_record.py`):
```diff
--- before (restored text)
    missing = [n for n in seat_map_module.roster_for(lane_basis) if n not in roster]
+++ neutralized
    missing = [n for n in seat_map_module.PANEL_ROSTER if n not in roster]
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_review_record.py::test_move_up_holds_a_no_floor_basis_to_the_three_seat_roster -q -p no:cacheprovider
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_move_up_holds_a_no_floor_basis_to_the_three_seat_roster _________

    def test_move_up_holds_a_no_floor_basis_to_the_three_seat_roster():
        # axis: the move-up check requires the roster the lane basis calls for, not the full panel — see bite-proof record wo_a_1797_roster
        assert len(THREE_SEAT_MAP["roster"]) == 3
>       assert rr._move_up_blocker(THREE_SEAT_MAP, frozenset(["anthropic"]), NO_FLOOR_BASIS) is None
E       assert "the seat map's roster omits a panel seat: security-reviewer, premortem-reviewer" is None
E        +  where "the seat map's roster omits a panel seat: security-reviewer, premortem-reviewer" = <function _move_up_blocker at 0x7f61daaadbc0>({'seats': {'code-reviewer': {'vendor': 'codex', 'model': 'gpt-6.1-sol', 'effort': 'xhigh', 'tier': 'reviewer-deep', .....: 'xhigh', 'tier': 'reviewer', ...}}, 'degradations': [], 'seed': 0, 'liveVendors': ['codex', 'cursor', 'gemini'], ...}, frozenset({'anthropic'}), {'floor': None})
E        +    where <function _move_up_blocker at 0x7f61daaadbc0> = rr._move_up_blocker
E        +    and   frozenset({'anthropic'}) = frozenset(['anthropic'])

<repo>/plugins/superheroes/lib/tests/test_review_record.py:2368: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_review_record.py::test_move_up_holds_a_no_floor_basis_to_the_three_seat_roster
1 failed in 0.15s
red exit: 1
```

**restore:** the inverse text swap of the neutralization above (no `git checkout`, `git restore`, `git reset` or `git stash`).

**restore receipt** (restored line, `review_record.py:1103`):
```
    missing = [n for n in seat_map_module.roster_for(lane_basis) if n not in roster]
```
sha256 after the restore (identical to the baseline):
```
6abf5b4038f36b353c940748c27d05ce3d2177edd29aa32278edbb5408f5e853  plugins/superheroes/lib/seat_map.py
d6d8454a49d8e7fe8920443e8dd8300869bdcf559c0edc26b48722f8acf70fb1  plugins/superheroes/lib/review_record.py
```

**raw green** (after restore):
```
.                                                                        [100%]
1 passed in 0.15s
green exit: 0
```
