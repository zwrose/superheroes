# Bite-proof record: wo_adopt_retired_seats_2529

Detector: `plugins/superheroes/lib/tests/test_adopt_version_retired_seats_2529.py` (retired-seat fields of
`adopt_version.py plan`). Guarded code: `plugins/superheroes/lib/adopt_version.py` (`_tree_seats`,
`_retired_seats`, `_project_pin_seats`, and the `retiredSeatPins` line in `_plan`).
Rubric: `plugins/superheroes/rubric/bite-proof.md`.

Declared guarded-element set (from the work order): E1 to E5 below, one neutralization of the production
code each. Each was applied with one targeted edit, the detector file was run by the order's one test
command (`scripts/pinned-python -B -m pytest plugins/superheroes/lib/tests/test_adopt_version_retired_seats_2529.py -q -p no:cacheprovider`,
600000 ms Bash timeout; the order allows no other form, so each red is the whole file, not a single node), and
the edit was undone by the inverse edit. One green run closes the record (the order's budget allows one).

Redaction: pytest's scratch directories (under the sandbox temp area) are written `<tmp>`, and the
worktree prefix on the test file path (`/home/user/wt-2529-b/`) is dropped, in the captures below; the
other lines were not altered, except that the elided blocks are marked where they were left out. No secrets, tokens or private URLs appear. Every capture is
under 32 KiB. The `UV_NATIVE_TLS` warning line is the launcher's own, kept as printed.

Two disclosures about the run order, in the order they happened:

- E1 was run twice. The first red ran against an earlier version of the test file; E2 then showed that
  version's alias test could not bite (see E2), so the alias test was changed and E1 was redone against the
  final file. Only the final-file red is reproduced here. The earlier E1 red failed the same three tests
  (`test_dropped_seat_...`, `test_no_seat_pins_...`, `test_plan_writes_nothing_...`).
- E2's first attempt did not go red: with a two-release span, `ver` is the `to` tree, so the `to`-tree alias
  check excuses the seat and ignoring `ver`'s aliases changes nothing. The alias test gained a second case
  (`alias-in-middle-only`: the alias sits in the middle release, absent from `to`) that isolates the
  `ver`-alias check. That attempt was not run as a command and is not part of the record.

Pre-neutralization state of the guarded lines (re-read after the final restore, identical each time):

```
276:    seats = {v: _tree_seats(os.path.join(cache, v)) for v in span}
284:            if seat not in ver_known and seat not in ver_aliases \
285:                    and seat not in to_known and seat not in to_aliases:
287:    return out
349:    retired_pins = None if retired is None or pins is None else sorted(
350:        k for k in pins if k in {e["seat"] for e in retired})
```

## E1 — retired-seat detection

- Guarded element: the `out.append(...)` loop of `_retired_seats` and its returned list.
- Axis: a seat the earlier release knew and the later one dropped is reported as
  `{"seat", "version", "since"}`.
- Detector: `test_dropped_seat_is_named_and_the_pinned_one_is_listed` (first test; also reds
  `test_no_seat_pins_in_core_gives_an_empty_list_...` and `test_plan_writes_nothing_...`).
- Neutralization (readable span reports nothing): the last line of `_retired_seats`, `    return out`,
  became `    return []`.
- Raw red (first failure block shown in full; the other two blocks have the same shape and assert the same
  `retiredSeats` / `retiredSeatPins` values, elided here, about 2 KiB):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F........F.F.                                                            [100%]
=================================== FAILURES ===================================
___________ test_dropped_seat_is_named_and_the_pinned_one_is_listed ____________

capsys = <_pytest.capture.CaptureFixture object at 0x7f49a9466ea0>
tmp_path = PosixPath('<tmp>/test_dropped_seat_is_named_and0')

    def test_dropped_seat_is_named_and_the_pinned_one_is_listed(capsys, tmp_path):
        cache = tmp_path / "cache"
        _mkver(cache, "0.1.0", known=("code-reviewer", "grounding-seat"))
        _mkver(cache, "0.2.0", known=("code-reviewer",))
        proj = _seed_project(tmp_path, _pins("grounding-seat", "code-reviewer"))
        code, data = _plan(capsys, cache, "0.1.0", "0.2.0", proj)
        assert code == 0
>       assert data["retiredSeats"] == [{"seat": "grounding-seat", "version": "0.2.0", "since": "0.1.0"}]
E       AssertionError: assert [] == [{'seat': 'gr...ce': '0.1.0'}]
E         
E         Right contains one more item: {'seat': 'grounding-seat', 'version': '0.2.0', 'since': '0.1.0'}
E         Use -v to get more diff

plugins/superheroes/lib/tests/test_adopt_version_retired_seats_2529.py:97: AssertionError
[... blocks for test_no_seat_pins_in_core_gives_an_empty_list_while_the_seat_is_still_listed and
 test_plan_writes_nothing_to_the_project_the_store_or_any_version_tree elided: same cause ...]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_adopt_version_retired_seats_2529.py::test_dropped_seat_is_named_and_the_pinned_one_is_listed
FAILED plugins/superheroes/lib/tests/test_adopt_version_retired_seats_2529.py::test_no_seat_pins_in_core_gives_an_empty_list_while_the_seat_is_still_listed
FAILED plugins/superheroes/lib/tests/test_adopt_version_retired_seats_2529.py::test_plan_writes_nothing_to_the_project_the_store_or_any_version_tree
3 failed, 10 passed in 6.09s
```

- Restore: inverse edit, `    return []` back to `    return out`.
- Restore receipt: line 287 reads `    return out`.
- Green: the single closing green run below.

## E2 — alias exclusion

- Guarded element: `seat not in ver_aliases` in the `_retired_seats` condition (line 284).
- Axis: a seat dropped from `KNOWN_SEATS` but kept as a `LEGACY_SEAT_ALIASES` key in the newer tree is not
  retired, including when that newer tree is a middle release and not the `to` tree.
- Detector: `test_seat_kept_as_a_legacy_alias_is_not_retired[alias-in-middle-only]` (the `alias-in-to`
  case stays green under this neutralization, as it must: the `to`-tree check excuses it).
- Neutralization (ignore `ver`'s aliases): `if seat not in ver_known and seat not in ver_aliases \`
  became `if seat not in ver_known \`.
- Raw red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
..F..........                                                            [100%]
=================================== FAILURES ===================================
____ test_seat_kept_as_a_legacy_alias_is_not_retired[alias-in-middle-only] _____

capsys = <_pytest.capture.CaptureFixture object at 0x7f19d8d24170>
tmp_path = PosixPath('<tmp>/test_seat_kept_as_a_legacy_ali1')
span = (('0.1.0', ('code-reviewer', 'old-seat'), ()), ('0.2.0', ('code-reviewer',), ('old-seat',)), ('0.3.0', ('code-reviewer', 'new-seat'), ()))

    @pytest.mark.parametrize("span", [
        pytest.param((("0.1.0", ("code-reviewer", "old-seat"), ()),
                      ("0.2.0", ("code-reviewer",), ("old-seat",))), id="alias-in-to"),
        # the alias sits only in the middle release, so the `to` tree's own check cannot excuse the seat
        pytest.param((("0.1.0", ("code-reviewer", "old-seat"), ()),
                      ("0.2.0", ("code-reviewer",), ("old-seat",)),
                      ("0.3.0", ("code-reviewer", "new-seat"), ())), id="alias-in-middle-only"),
    ])
    def test_seat_kept_as_a_legacy_alias_is_not_retired(capsys, tmp_path, span):
        cache = tmp_path / "cache"
        for ver, known, aliases in span:
            _mkver(cache, ver, known=known, aliases=aliases)
        proj = _seed_project(tmp_path, _pins("old-seat"))
        code, data = _plan(capsys, cache, span[0][0], span[-1][0], proj)
        assert code == 0
>       assert data["retiredSeats"] == []
E       AssertionError: assert [{'seat': 'ol...ce': '0.1.0'}] == []
E         
E         Left contains one more item: {'seat': 'old-seat', 'version': '0.2.0', 'since': '0.1.0'}
E         Use -v to get more diff

plugins/superheroes/lib/tests/test_adopt_version_retired_seats_2529.py:117: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_adopt_version_retired_seats_2529.py::test_seat_kept_as_a_legacy_alias_is_not_retired[alias-in-middle-only]
1 failed, 12 passed in 6.17s
```

- Restore: inverse edit, `if seat not in ver_known \` back to
  `if seat not in ver_known and seat not in ver_aliases \`.
- Restore receipt: line 284 reads `            if seat not in ver_known and seat not in ver_aliases \`.
- Green: the closing green run below.

## E3 — came-back exclusion

- Guarded element: `seat not in to_known and seat not in to_aliases` in the `_retired_seats` condition
  (line 285).
- Axis: a seat dropped in a middle release and known again in the `to` tree is not retired.
- Detector: `test_seat_dropped_in_the_middle_and_back_in_to_is_not_retired`.
- Neutralization (skip the `to`-tree check): the two condition lines became
  `            if seat not in ver_known and seat not in ver_aliases:`.
- Raw red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
...F.........                                                            [100%]
=================================== FAILURES ===================================
________ test_seat_dropped_in_the_middle_and_back_in_to_is_not_retired _________

capsys = <_pytest.capture.CaptureFixture object at 0x7f8c542671a0>
tmp_path = PosixPath('<tmp>/test_seat_dropped_in_the_middl0')

    def test_seat_dropped_in_the_middle_and_back_in_to_is_not_retired(capsys, tmp_path):
        cache = tmp_path / "cache"
        _mkver(cache, "0.1.0", known=("code-reviewer", "wanderer"))
        _mkver(cache, "0.2.0", known=("code-reviewer",))
        _mkver(cache, "0.3.0", known=("code-reviewer", "wanderer"))
        proj = _seed_project(tmp_path, _pins("wanderer"))
        code, data = _plan(capsys, cache, "0.1.0", "0.3.0", proj)
        assert code == 0
>       assert data["retiredSeats"] == []
E       AssertionError: assert [{'seat': 'wa...ce': '0.1.0'}] == []
E         
E         Left contains one more item: {'seat': 'wanderer', 'version': '0.2.0', 'since': '0.1.0'}
E         Use -v to get more diff

plugins/superheroes/lib/tests/test_adopt_version_retired_seats_2529.py:129: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_adopt_version_retired_seats_2529.py::test_seat_dropped_in_the_middle_and_back_in_to_is_not_retired
1 failed, 12 passed in 5.98s
```

- Restore: inverse edit, the one condition line back to the two lines
  `if seat not in ver_known and seat not in ver_aliases \` / `and seat not in to_known and seat not in to_aliases:`.
- Restore receipt: lines 284-285 quoted in the pre-neutralization block above.
- Green: the closing green run below.

## E4 — unreadable tree gives `null`

- Guarded element: `if any(s is None for s in seats.values()): return None` in `_retired_seats` (line 277),
  fed by `_tree_seats` returning `None`.
- Axis: a tree in the span whose seat_map is missing, raises, prints non-JSON, reads wrong-typed or times
  out makes `retiredSeats` and `retiredSeatPins` `null`, and the plan still succeeds.
- Detector: `test_unreadable_tree_makes_both_fields_null_and_the_plan_still_succeeds` (5 cases).
- Neutralization (an unreadable tree counts as an empty known set): line 276 became
  `    seats = {v: _tree_seats(os.path.join(cache, v)) or (set(), set()) for v in span}`.
- Raw red (all five cases fail with the same assertion; the first block is shown, the other four, about
  7 KiB, are elided; the summary lists all five):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
....FFFFF....                                                            [100%]
=================================== FAILURES ===================================
_ test_unreadable_tree_makes_both_fields_null_and_the_plan_still_succeeds[module-missing] _

capsys = <_pytest.capture.CaptureFixture object at 0x7fe88900e690>
tmp_path = PosixPath('<tmp>/test_unreadable_tree_makes_bot0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7fe88900e780>
broken = False

    @pytest.mark.parametrize("broken", [
        pytest.param(False, id="module-missing"),
        pytest.param("raise RuntimeError('no seats')\n", id="raises-on-import"),
        pytest.param("print('noise')\nKNOWN_SEATS = ('a',)\n", id="prints-non-json"),
        pytest.param("KNOWN_SEATS = (1, 2)\n", id="wrong-typed"),
        pytest.param("import time\ntime.sleep(60)\n", id="times-out"),
    ])
    def test_unreadable_tree_makes_both_fields_null_and_the_plan_still_succeeds(
            capsys, tmp_path, monkeypatch, broken):
        monkeypatch.setattr(av, "STAMP_TIMEOUT_SECONDS", 2)
        cache = tmp_path / "cache"
        _mkver(cache, "0.1.0", known=("code-reviewer", "grounding-seat"))
        _mkver(cache, "0.2.0", seat_map=broken)
        _mkver(cache, "0.3.0", known=("code-reviewer",))
        proj = _seed_project(tmp_path, _pins("grounding-seat"))
        code, data = _plan(capsys, cache, "0.1.0", "0.3.0", proj)
        assert code == 0 and data["ok"] is True
>       assert data["retiredSeats"] is None
E       AssertionError: assert [{'seat': 'grounding-seat', 'version': '0.2.0', 'since': '0.1.0'}] is None

plugins/superheroes/lib/tests/test_adopt_version_retired_seats_2529.py:150: AssertionError
[... blocks for raises-on-import, prints-non-json, wrong-typed and times-out elided: identical assertion
 and line 150 in each ...]
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_adopt_version_retired_seats_2529.py::test_unreadable_tree_makes_both_fields_null_and_the_plan_still_succeeds[module-missing]
FAILED plugins/superheroes/lib/tests/test_adopt_version_retired_seats_2529.py::test_unreadable_tree_makes_both_fields_null_and_the_plan_still_succeeds[raises-on-import]
FAILED plugins/superheroes/lib/tests/test_adopt_version_retired_seats_2529.py::test_unreadable_tree_makes_both_fields_null_and_the_plan_still_succeeds[prints-non-json]
FAILED plugins/superheroes/lib/tests/test_adopt_version_retired_seats_2529.py::test_unreadable_tree_makes_both_fields_null_and_the_plan_still_succeeds[wrong-typed]
FAILED plugins/superheroes/lib/tests/test_adopt_version_retired_seats_2529.py::test_unreadable_tree_makes_both_fields_null_and_the_plan_still_succeeds[times-out]
5 failed, 8 passed in 6.13s
```

- Restore: inverse edit, `... _tree_seats(os.path.join(cache, v)) or (set(), set()) for v in span}` back to
  `... _tree_seats(os.path.join(cache, v)) for v in span}`.
- Restore receipt: line 276 reads
  `    seats = {v: _tree_seats(os.path.join(cache, v)) for v in span}`.
- Green: the closing green run below.

## E5 — pin intersection

- Guarded element: the `sorted(k for k in pins if k in {e["seat"] for e in retired})` intersection in
  `_plan` (lines 349-350).
- Axis: `retiredSeatPins` lists the pinned seat keys that appear as a retired `seat`, and only those
  (`code-reviewer`, pinned but live, is left out).
- Detector: `test_dropped_seat_is_named_and_the_pinned_one_is_listed` (also reds the read-only test, which
  asserts `retiredSeatPins == ["grounding-seat"]`).
- Neutralization (never list a pin): the `retired_pins = ...` expression's `sorted(...)` branch became `[]`:
  `retired_pins = None if retired is None or pins is None else []`.
- Raw red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F..........F.                                                            [100%]
=================================== FAILURES ===================================
___________ test_dropped_seat_is_named_and_the_pinned_one_is_listed ____________

capsys = <_pytest.capture.CaptureFixture object at 0x7f1f079f2cf0>
tmp_path = PosixPath('<tmp>/test_dropped_seat_is_named_and0')

    def test_dropped_seat_is_named_and_the_pinned_one_is_listed(capsys, tmp_path):
        cache = tmp_path / "cache"
        _mkver(cache, "0.1.0", known=("code-reviewer", "grounding-seat"))
        _mkver(cache, "0.2.0", known=("code-reviewer",))
        proj = _seed_project(tmp_path, _pins("grounding-seat", "code-reviewer"))
        code, data = _plan(capsys, cache, "0.1.0", "0.2.0", proj)
        assert code == 0
        assert data["retiredSeats"] == [{"seat": "grounding-seat", "version": "0.2.0", "since": "0.1.0"}]
>       assert data["retiredSeatPins"] == ["grounding-seat"]
E       AssertionError: assert [] == ['grounding-seat']
E         
E         Right contains one more item: 'grounding-seat'
E         Use -v to get more diff

plugins/superheroes/lib/tests/test_adopt_version_retired_seats_2529.py:98: AssertionError
____ test_plan_writes_nothing_to_the_project_the_store_or_any_version_tree _____

capsys = <_pytest.capture.CaptureFixture object at 0x7f1f079f4f80>
tmp_path = PosixPath('<tmp>/test_plan_writes_nothing_to_th0')
_store = PosixPath('<tmp>/test_plan_writes_nothing_to_th0/store')

    def test_plan_writes_nothing_to_the_project_the_store_or_any_version_tree(capsys, tmp_path, _store):
        cache = tmp_path / "cache"
        _mkver(cache, "0.1.0", known=("code-reviewer", "grounding-seat"))
        _mkver(cache, "0.2.0", known=("code-reviewer",))
        proj = _seed_project(tmp_path, _pins("grounding-seat"))
        core_before = (proj / ".claude" / "superheroes" / "core.md").read_bytes()
        before = _snapshot(cache, proj, _store)
        code, data = _plan(capsys, cache, "0.1.0", "0.2.0", proj)
>       assert code == 0 and data["retiredSeatPins"] == ["grounding-seat"]
E       AssertionError: assert (0 == 0 and [] == ['grounding-seat']
E         
E         Right contains one more item: 'grounding-seat'
E         Use -v to get more diff)

plugins/superheroes/lib/tests/test_adopt_version_retired_seats_2529.py:185: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_adopt_version_retired_seats_2529.py::test_dropped_seat_is_named_and_the_pinned_one_is_listed
FAILED plugins/superheroes/lib/tests/test_adopt_version_retired_seats_2529.py::test_plan_writes_nothing_to_the_project_the_store_or_any_version_tree
2 failed, 11 passed in 6.44s
```

- Restore: inverse edit, `else []` back to
  `else sorted(` / `k for k in pins if k in {e["seat"] for e in retired})`.
- Restore receipt: lines 349-350 quoted in the pre-neutralization block above.
- Green: the closing green run below.

## Closing green (after the E5 restore; all five guarded lines back as quoted above)

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.............                                                            [100%]
13 passed in 6.33s
```

## Not covered by a neutralization

Declared set is E1 to E5. Elements of the new code with no neutralization of their own, listed as
unproven by the bite-proof (the file has assertions on them, none was mutated): the `from == to` early
return (`test_up_to_date_plan_reports_no_retired_seats_without_reading_a_tree` leaves the tree's seat_map
out, so a reading would turn the result `null`), and the three `_project_pin_seats` edges (absent core.md,
non-object `seatPins`, refused core.md; `test_pin_read_edges`).
