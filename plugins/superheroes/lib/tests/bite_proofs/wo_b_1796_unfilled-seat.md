# WO-B (#1796) bite-proof — unfilled seats: the panel never seats a maker family

**Provenance:** claude / sonnet (implementer), `plugins/superheroes/lib/seat_map.py`, `seat_map_receipts.py`, `conformance_probe.py`.

Declared guarded-element set (from the order): N1-N9. Each was neutralized by an exact text swap in production code only, the single detector node was run red, the neutralization was undone by the inverse text swap, and the same node was run green. Temp paths are the only redaction (`<tmp>` for the pytest temp root, `<repo>` for the worktree root); nothing else was edited.

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| N1 | maker filter, no same-family fill (`seat_map.py` `build()`, per-seat maker filter) | a seat whose only candidates are makers is left empty, never filled with a maker family | `test_unfilled_seat_invariant_no_seat_carries_a_maker_family` |
| N2 | maker filter, no secondary-maker fill (`seat_map.py` `build()`, per-seat maker filter) | an extra maker family is barred exactly like the author family; no author-only fallback | `test_e2_author_plus_extra_maker_live_leaves_every_seat_unfilled` |
| N3 | `_backfill` maker filter (`seat_map.py` `build()`, both backfill loops) | a seat emptied for a non-maker reason is never backfilled with a maker family | `test_backfill_for_a_non_maker_reason_never_returns_a_maker_family` |
| N4 | maker-family pin leaves the seat unfilled (`seat_map.py` `build()`, pin handling) | a pin to a maker family does not seat it | `test_e3_maker_family_pin_leaves_its_seat_unfilled_and_others_compose` |
| N5 | `verify()` tolerates an unfilled seat (`seat_map.py` `verify()`) | an unfilled seat is a known not-run seat, not a missing, malformed, unresolvable or maker-family seat | `test_e5_verify_and_receipt_tolerate_unfilled_seats` |
| N6 | receipt `makerFamilies` (`seat_map.py` `to_receipt`) | the receipt names the maker families it composed against | `test_build_and_receipt_name_the_maker_families_and_the_roster` |
| N7 | receipt `roster` (`seat_map.py` `to_receipt`) | the receipt names the roster it composed against | `test_build_and_receipt_name_the_maker_families_and_the_roster` |
| N8 | `--maker-family` reaching `build` (`seat_map.py` `main`) | a maker family passed on the compose command line is excluded from every seat | `test_e6_compose_maker_family_flag_excludes_that_family` |
| N9 | conformance probe parks on `seat-unfilled` (`conformance_probe.py` `preflight_entry`) | a composed map with an unfilled seat parks the full lane | `test_e7_preflight_entry_parks_on_a_real_unfilled_seat` |

## Disclosures

- N6 and N7 share one detector node; each was neutralized separately and fails at its own assertion.
- Not separately neutralized (the order allowed 18 node runs, two per declared element): the `emit_receipt_seat_map` merge of `makerFamilies` (sorted union) and `roster` (last-wins) in `seat_map_receipts.py`. It is exercised green by `test_emit_receipt_seat_map_merges_maker_families_and_roster` and `test_emit_receipt_seat_map_carries_what_a_composed_receipt_names`, with no red shown. Listed as unproven.
- Restore receipts: the neutralized line(s) are quoted back as they stand in the file after the inverse edit, and the sha256 of `seat_map.py` and `conformance_probe.py` is compared with the value taken before the neutralization.

---

## N1 — maker filter, no same-family fill (`seat_map.py` `build()`, per-seat maker filter)

- **axis:** a seat whose only candidates are makers is left empty, never filled with a maker family

**neutralization** (`plugins/superheroes/lib/seat_map.py`):
```diff
--- before (restored text)
            eligible = [cfg for cfg in eligible if cfg["family"] not in makers]
            if not eligible:
                maker_emptied_seats.add(seat)
+++ neutralized
            eligible = [cfg for cfg in eligible if cfg["family"] not in makers] or eligible
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_seat_map.py::test_unfilled_seat_invariant_no_seat_carries_a_maker_family -q -p no:cacheprovider
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_unfilled_seat_invariant_no_seat_carries_a_maker_family __________

    def test_unfilled_seat_invariant_no_seat_carries_a_maker_family():
        vendor_sets = [[], ["claude"], ["codex"], ["claude", "codex"], ["claude", "codex", "cursor"]]
        for live in vendor_sets:
            for author in ("anthropic", "openai", "xai"):
                for extra in (frozenset(), frozenset({"openai"})):
                    for seed in (0, 1, 2):
                        m = SM.build(
                            SM.PANEL_ROSTER, live, author, "anthropic", seed,
                            extra_maker_families=extra,
                        )
                        makers = {author} | set(extra)
                        assert m["makerFamilies"] == sorted(makers)
                        for seat in SM.PANEL_ROSTER:
                            cfg = m["seats"][seat]
                            ctx = (live, author, sorted(extra), seed, seat)
>                           assert cfg["family"] not in makers, ctx
E                           AssertionError: ([], 'anthropic', [], 0, 'architecture-reviewer')
E                           assert 'anthropic' not in {'anthropic'}

<repo>/plugins/superheroes/lib/tests/test_seat_map.py:4190: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_unfilled_seat_invariant_no_seat_carries_a_maker_family
1 failed in 0.46s
red exit: 1
```

**restore:** the inverse text swap of the neutralization above (the "before" text put back; no `git checkout`, `git restore`, `git reset` or `git stash`).

**restore receipt** (restored text as it stands in `plugins/superheroes/lib/seat_map.py`):
```
            eligible = [cfg for cfg in eligible if cfg["family"] not in makers]
            if not eligible:
                maker_emptied_seats.add(seat)
```

sha256 before the neutralization(s) in force at restore time:
```
8710b67ce064620cce47ddb1d92761dbc43d157d23a789788969f62c06db1a4d  seat_map.py
44502d22a72dda6a7d3828ecd4661d1987e423e4fb6b6870c5b54dfcbb554c9f  conformance_probe.py
```
sha256 after the restore (identical):
```
8710b67ce064620cce47ddb1d92761dbc43d157d23a789788969f62c06db1a4d  seat_map.py
44502d22a72dda6a7d3828ecd4661d1987e423e4fb6b6870c5b54dfcbb554c9f  conformance_probe.py
```

**raw green** (after restore):
```
.                                                                        [100%]
1 passed in 0.12s
green exit: 0
```

---

## N2 — maker filter, no secondary-maker fill (`seat_map.py` `build()`, per-seat maker filter)

- **axis:** an extra maker family is barred exactly like the author family; no author-only fallback

**neutralization** (`plugins/superheroes/lib/seat_map.py`):
```diff
--- before (restored text)
            eligible = [cfg for cfg in eligible if cfg["family"] not in makers]
            if not eligible:
                maker_emptied_seats.add(seat)
+++ neutralized
            eligible = [cfg for cfg in eligible if cfg["family"] not in makers] or [
                cfg for cfg in eligible if cfg["family"] != author_family
            ]
            if not eligible:
                maker_emptied_seats.add(seat)
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_seat_map.py::test_e2_author_plus_extra_maker_live_leaves_every_seat_unfilled -q -p no:cacheprovider
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_e2_author_plus_extra_maker_live_leaves_every_seat_unfilled ________

    def test_e2_author_plus_extra_maker_live_leaves_every_seat_unfilled():
        m = SM.build(
            SM.PANEL_ROSTER,
            ["claude", "codex"],
            "anthropic",
            "openai",
            3,
            extra_maker_families=frozenset({"openai"}),
        )
>       _assert_all_unfilled(m)

<repo>/plugins/superheroes/lib/tests/test_seat_map.py:4012: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

m = {'seats': {'architecture-reviewer': {'vendor': 'codex', 'model': 'gpt-6.1-sol', 'effort': 'xhigh', 'tier': 'reviewer-d...'relaxed critical-diversity — no assignment spanned ≥2 families'}], 'seed': 3, 'liveVendors': ['claude', 'codex'], ...}
roster = None

    def _assert_all_unfilled(m, roster=None):
        for seat in roster or SM.PANEL_ROSTER:
            cfg = m["seats"][seat]
>           assert cfg["source"] == "unfilled", seat
E           AssertionError: architecture-reviewer
E           assert 'rotated' == 'unfilled'
E             
E             - unfilled
E             + rotated

<repo>/plugins/superheroes/lib/tests/test_seat_map.py:3982: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_e2_author_plus_extra_maker_live_leaves_every_seat_unfilled
1 failed in 4.05s
red exit: 1
```

**restore:** the inverse text swap of the neutralization above (the "before" text put back; no `git checkout`, `git restore`, `git reset` or `git stash`).

**restore receipt** (restored text as it stands in `plugins/superheroes/lib/seat_map.py`):
```
            eligible = [cfg for cfg in eligible if cfg["family"] not in makers]
            if not eligible:
                maker_emptied_seats.add(seat)
```

sha256 before the neutralization(s) in force at restore time:
```
8710b67ce064620cce47ddb1d92761dbc43d157d23a789788969f62c06db1a4d  seat_map.py
44502d22a72dda6a7d3828ecd4661d1987e423e4fb6b6870c5b54dfcbb554c9f  conformance_probe.py
```
sha256 after the restore (identical):
```
8710b67ce064620cce47ddb1d92761dbc43d157d23a789788969f62c06db1a4d  seat_map.py
44502d22a72dda6a7d3828ecd4661d1987e423e4fb6b6870c5b54dfcbb554c9f  conformance_probe.py
```

**raw green** (after restore):
```
.                                                                        [100%]
1 passed in 0.10s
green exit: 0
```

---

## N3 — `_backfill` maker filter (`seat_map.py` `build()`, both backfill loops)

- **axis:** a seat emptied for a non-maker reason is never backfilled with a maker family

**neutralization** (`plugins/superheroes/lib/seat_map.py`):
```diff
--- before (restored text)
                if cfg is not None and cfg["family"] not in makers:
+++ neutralized
                if cfg is not None:
--- before (restored text)
            if cfg is not None and cfg["family"] not in makers:
+++ neutralized
            if cfg is not None:
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_seat_map.py::test_backfill_for_a_non_maker_reason_never_returns_a_maker_family -q -p no:cacheprovider
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_backfill_for_a_non_maker_reason_never_returns_a_maker_family _______

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f28852049d0>

    def test_backfill_for_a_non_maker_reason_never_returns_a_maker_family(monkeypatch):
        # no reviewer-deep cell exists at all, so every strong seat is empty for a reason that is not the
        # maker filter; the reviewer-tier backfill may seat a non-maker but never the author's family
        real_matrix = SM.matrix_config
    
        def _no_reviewer_deep(tier, vendor):
            if tier == "reviewer-deep":
                return None
            return real_matrix(tier, vendor)
    
        monkeypatch.setattr(SM, "matrix_config", _no_reviewer_deep)
        only_maker = SM.build(SM.PANEL_ROSTER, ["claude"], "anthropic", "openai", 0)
        with_other = SM.build(SM.PANEL_ROSTER, THREE_VENDORS, "anthropic", "openai", 0)
        for seat in SM.STRONG_TIER_SEATS:
>           assert only_maker["seats"][seat]["source"] == "unfilled", seat
E           AssertionError: security-reviewer
E           assert 'backfill' == 'unfilled'
E             
E             - unfilled
E             + backfill

<repo>/plugins/superheroes/lib/tests/test_seat_map.py:4218: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_backfill_for_a_non_maker_reason_never_returns_a_maker_family
1 failed in 0.14s
red exit: 1
```

**restore:** the inverse text swap of the neutralization above (the "before" text put back; no `git checkout`, `git restore`, `git reset` or `git stash`).

**restore receipt** (restored text as it stands in `plugins/superheroes/lib/seat_map.py`):
```
                if cfg is not None and cfg["family"] not in makers:
            if cfg is not None and cfg["family"] not in makers:
```

sha256 before the neutralization(s) in force at restore time:
```
8710b67ce064620cce47ddb1d92761dbc43d157d23a789788969f62c06db1a4d  seat_map.py
44502d22a72dda6a7d3828ecd4661d1987e423e4fb6b6870c5b54dfcbb554c9f  conformance_probe.py
```
sha256 after the restore (identical):
```
8710b67ce064620cce47ddb1d92761dbc43d157d23a789788969f62c06db1a4d  seat_map.py
44502d22a72dda6a7d3828ecd4661d1987e423e4fb6b6870c5b54dfcbb554c9f  conformance_probe.py
```

**raw green** (after restore):
```
.                                                                        [100%]
1 passed in 0.10s
green exit: 0
```

---

## N4 — maker-family pin leaves the seat unfilled (`seat_map.py` `build()`, pin handling)

- **axis:** a pin to a maker family does not seat it

**neutralization** (`plugins/superheroes/lib/seat_map.py`):
```diff
--- before (restored text)
            if pin_seat in MAKER_EXCLUDED_SEATS and fam in makers:
+++ neutralized
            if False and pin_seat in MAKER_EXCLUDED_SEATS and fam in makers:
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_seat_map.py::test_e3_maker_family_pin_leaves_its_seat_unfilled_and_others_compose -q -p no:cacheprovider
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_e3_maker_family_pin_leaves_its_seat_unfilled_and_others_compose _____

    def test_e3_maker_family_pin_leaves_its_seat_unfilled_and_others_compose():
        pins = {"code-reviewer": {"vendor": "claude"}}
        m = SM.build(SM.PANEL_ROSTER, THREE_VENDORS, "anthropic", "openai", 0, pins=pins)
>       assert m["seats"]["code-reviewer"]["source"] == "unfilled"
E       AssertionError: assert 'pinned' == 'unfilled'
E         
E         - unfilled
E         + pinned

<repo>/plugins/superheroes/lib/tests/test_seat_map.py:4023: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_e3_maker_family_pin_leaves_its_seat_unfilled_and_others_compose
1 failed in 0.15s
red exit: 1
```

**restore:** the inverse text swap of the neutralization above (the "before" text put back; no `git checkout`, `git restore`, `git reset` or `git stash`).

**restore receipt** (restored text as it stands in `plugins/superheroes/lib/seat_map.py`):
```
            if pin_seat in MAKER_EXCLUDED_SEATS and fam in makers:
```

sha256 before the neutralization(s) in force at restore time:
```
8710b67ce064620cce47ddb1d92761dbc43d157d23a789788969f62c06db1a4d  seat_map.py
44502d22a72dda6a7d3828ecd4661d1987e423e4fb6b6870c5b54dfcbb554c9f  conformance_probe.py
```
sha256 after the restore (identical):
```
8710b67ce064620cce47ddb1d92761dbc43d157d23a789788969f62c06db1a4d  seat_map.py
44502d22a72dda6a7d3828ecd4661d1987e423e4fb6b6870c5b54dfcbb554c9f  conformance_probe.py
```

**raw green** (after restore):
```
.                                                                        [100%]
1 passed in 0.10s
green exit: 0
```

---

## N5 — `verify()` tolerates an unfilled seat (`seat_map.py` `verify()`)

- **axis:** an unfilled seat is a known not-run seat, not a missing, malformed, unresolvable or maker-family seat

**neutralization** (`plugins/superheroes/lib/seat_map.py`):
```diff
--- before (restored text)
            if not isinstance(cfg, dict) or _is_unfilled(cfg):
                continue
            seat_fam = _seat_family(seat, cfg)
+++ neutralized
            if not isinstance(cfg, dict):
                continue
            seat_fam = _seat_family(seat, cfg)
--- before (restored text)
        elif _is_unfilled(seats[seat]):
            # a known not-run seat, disclosed as a `seat-unfilled` degradation
            continue
        elif not isinstance(seats[seat], dict):
+++ neutralized
        elif not isinstance(seats[seat], dict):
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_seat_map.py::test_e5_verify_and_receipt_tolerate_unfilled_seats -q -p no:cacheprovider
```

**note:** The first restore attempt aborted before writing (its pattern matched two places), leaving N5 applied; the N6 red below was then captured with N5 also applied (N5 changes only `verify()`; the N6 failure is a `KeyError` on the receipt key). The pattern was anchored, N6 and N5 were restored by their inverse edits, and the N5 green was run after the restore.

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_e5_verify_and_receipt_tolerate_unfilled_seats ______________

    def test_e5_verify_and_receipt_tolerate_unfilled_seats():
        m = SM.build(SM.PANEL_ROSTER, ["claude"], "anthropic", "openai", 0)
        violations = SM.verify(m, "anthropic")
        blocked = {"missing-seat", "malformed", "unresolvable-seat-vendor", "maker-family"}
>       assert not [v for v in violations if v.get("constraint") in blocked], violations
E       AssertionError: [{'constraint': 'critical-diversity'}, {'seat': 'architecture-reviewer', 'constraint': 'unresolvable-seat-vendor'}, {'...constraint': 'unresolvable-seat-vendor'}, {'seat': 'security-reviewer', 'constraint': 'unresolvable-seat-vendor'}, ...]
E       assert not [{'seat': 'architecture-reviewer', 'constraint': 'unresolvable-seat-vendor'}, {'seat': 'code-reviewer', 'constraint': ...iewer', 'constraint': 'unresolvable-seat-vendor'}, {'seat': 'test-reviewer', 'constraint': 'unresolvable-seat-vendor'}]

<repo>/plugins/superheroes/lib/tests/test_seat_map.py:4073: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_e5_verify_and_receipt_tolerate_unfilled_seats
1 failed in 0.14s
red exit: 1
```

**restore:** the inverse text swap of the neutralization above (the "before" text put back; no `git checkout`, `git restore`, `git reset` or `git stash`).

**restore receipt** (restored text as it stands in `plugins/superheroes/lib/seat_map.py`):
```
            if not isinstance(cfg, dict) or _is_unfilled(cfg):
                continue
            seat_fam = _seat_family(seat, cfg)
        elif _is_unfilled(seats[seat]):
            # a known not-run seat, disclosed as a `seat-unfilled` degradation
            continue
        elif not isinstance(seats[seat], dict):
```

sha256 before the neutralization(s) in force at restore time:
```
8710b67ce064620cce47ddb1d92761dbc43d157d23a789788969f62c06db1a4d  seat_map.py
44502d22a72dda6a7d3828ecd4661d1987e423e4fb6b6870c5b54dfcbb554c9f  conformance_probe.py
```
sha256 after the restore (identical):
```
8710b67ce064620cce47ddb1d92761dbc43d157d23a789788969f62c06db1a4d  seat_map.py
44502d22a72dda6a7d3828ecd4661d1987e423e4fb6b6870c5b54dfcbb554c9f  conformance_probe.py
```

**raw green** (after restore):
```
.                                                                        [100%]
1 passed in 0.10s
green exit: 0
```

---

## N6 — receipt `makerFamilies` (`seat_map.py` `to_receipt`)

- **axis:** the receipt names the maker families it composed against

**neutralization** (`plugins/superheroes/lib/seat_map.py`):
```diff
--- before (restored text)
        "violations": verify(seat_map, af),
        "makerFamilies": sorted(maker_families),
+++ neutralized
        "violations": verify(seat_map, af),
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_seat_map.py::test_build_and_receipt_name_the_maker_families_and_the_roster -q -p no:cacheprovider
```

**note:** Captured with the N5 neutralization still applied (see N5). The failing line is the receipt key lookup, which `verify()` does not touch. Restored by the inverse edit together with N5; the hash equals the pre-N5 hash recorded under N5.

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_build_and_receipt_name_the_maker_families_and_the_roster _________

    def test_build_and_receipt_name_the_maker_families_and_the_roster():
        m = SM.build(SM.PANEL_ROSTER, THREE_VENDORS, "anthropic", "openai", 0,
                     extra_maker_families=frozenset({"xai"}))
        assert m["makerFamilies"] == ["anthropic", "xai"]
        assert m["roster"] == list(SM.PANEL_ROSTER)
        receipt = SM.to_receipt(m, "anthropic")
>       assert receipt["makerFamilies"] == ["anthropic", "xai"]
               ^^^^^^^^^^^^^^^^^^^^^^^^
E       KeyError: 'makerFamilies'

<repo>/plugins/superheroes/lib/tests/test_seat_map.py:4154: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_build_and_receipt_name_the_maker_families_and_the_roster
1 failed in 0.14s
red exit: 1
```

**restore:** the inverse text swap of the neutralization above (the "before" text put back; no `git checkout`, `git restore`, `git reset` or `git stash`).

**restore receipt** (restored text as it stands in `plugins/superheroes/lib/seat_map.py`):
```
        "violations": verify(seat_map, af),
        "makerFamilies": sorted(maker_families),
```

sha256 before the neutralization(s) in force at restore time:
```
8710b67ce064620cce47ddb1d92761dbc43d157d23a789788969f62c06db1a4d  seat_map.py
44502d22a72dda6a7d3828ecd4661d1987e423e4fb6b6870c5b54dfcbb554c9f  conformance_probe.py
```
sha256 after the restore (identical):
```
8710b67ce064620cce47ddb1d92761dbc43d157d23a789788969f62c06db1a4d  seat_map.py
44502d22a72dda6a7d3828ecd4661d1987e423e4fb6b6870c5b54dfcbb554c9f  conformance_probe.py
```

**raw green** (after restore):
```
.                                                                        [100%]
1 passed in 0.10s
green exit: 0
```

---

## N7 — receipt `roster` (`seat_map.py` `to_receipt`)

- **axis:** the receipt names the roster it composed against

**neutralization** (`plugins/superheroes/lib/seat_map.py`):
```diff
--- before (restored text)
        "roster": roster,
    }
    role_pins, pins_usable
+++ neutralized
    }
    role_pins, pins_usable
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_seat_map.py::test_build_and_receipt_name_the_maker_families_and_the_roster -q -p no:cacheprovider
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_build_and_receipt_name_the_maker_families_and_the_roster _________

    def test_build_and_receipt_name_the_maker_families_and_the_roster():
        m = SM.build(SM.PANEL_ROSTER, THREE_VENDORS, "anthropic", "openai", 0,
                     extra_maker_families=frozenset({"xai"}))
        assert m["makerFamilies"] == ["anthropic", "xai"]
        assert m["roster"] == list(SM.PANEL_ROSTER)
        receipt = SM.to_receipt(m, "anthropic")
        assert receipt["makerFamilies"] == ["anthropic", "xai"]
>       assert receipt["roster"] == list(SM.PANEL_ROSTER)
               ^^^^^^^^^^^^^^^^^
E       KeyError: 'roster'

<repo>/plugins/superheroes/lib/tests/test_seat_map.py:4155: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_build_and_receipt_name_the_maker_families_and_the_roster
1 failed in 0.14s
red exit: 1
```

**restore:** the inverse text swap of the neutralization above (the "before" text put back; no `git checkout`, `git restore`, `git reset` or `git stash`).

**restore receipt** (restored text as it stands in `plugins/superheroes/lib/seat_map.py`):
```
        "roster": roster,
    }
    role_pins, pins_usable
```

sha256 before the neutralization(s) in force at restore time:
```
8710b67ce064620cce47ddb1d92761dbc43d157d23a789788969f62c06db1a4d  seat_map.py
44502d22a72dda6a7d3828ecd4661d1987e423e4fb6b6870c5b54dfcbb554c9f  conformance_probe.py
```
sha256 after the restore (identical):
```
8710b67ce064620cce47ddb1d92761dbc43d157d23a789788969f62c06db1a4d  seat_map.py
44502d22a72dda6a7d3828ecd4661d1987e423e4fb6b6870c5b54dfcbb554c9f  conformance_probe.py
```

**raw green** (after restore):
```
.                                                                        [100%]
1 passed in 0.10s
green exit: 0
```

---

## N8 — `--maker-family` reaching `build` (`seat_map.py` `main`)

- **axis:** a maker family passed on the compose command line is excluded from every seat

**neutralization** (`plugins/superheroes/lib/seat_map.py`):
```diff
--- before (restored text)
            extra_maker_families = frozenset(extra_maker_families or ()) | flag_makers
+++ neutralized
            pass
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_seat_map.py::test_e6_compose_maker_family_flag_excludes_that_family -q -p no:cacheprovider
```

**note:** The first green call for N8 was refused by the permission layer and did not run, so N8 stayed applied while the N9 red was captured; N8 touches only `main()` and the N9 path never reaches it. N8 and N9 were then restored by their inverse edits and each green was run.

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_e6_compose_maker_family_flag_excludes_that_family ____________

capsys = <_pytest.capture.CaptureFixture object at 0x7ff3163f9160>

    def test_e6_compose_maker_family_flag_excludes_that_family(capsys):
        argv = [
            "x", "compose",
            "--live-vendors", "claude,codex",
            "--author-family", "anthropic",
            "--narrative-family", "anthropic",
            "--pr-number", "1796",
        ]
        assert SM.main(argv) == 0
        without_flag = json.loads(capsys.readouterr().out)
        assert any(cfg["family"] == "openai" for cfg in without_flag["seats"].values())
    
        assert SM.main(argv + ["--maker-family", "openai"]) == 0
        receipt = json.loads(capsys.readouterr().out)
        for seat in SM.PANEL_ROSTER:
>           assert receipt["seats"][seat]["source"] == "unfilled", seat
E           AssertionError: architecture-reviewer
E           assert 'rotated' == 'unfilled'
E             
E             - unfilled
E             + rotated

<repo>/plugins/superheroes/lib/tests/test_seat_map.py:4107: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_map.py::test_e6_compose_maker_family_flag_excludes_that_family
1 failed in 0.16s
red exit: 1
```

**restore:** the inverse text swap of the neutralization above (the "before" text put back; no `git checkout`, `git restore`, `git reset` or `git stash`).

**restore receipt** (restored text as it stands in `plugins/superheroes/lib/seat_map.py`):
```
            extra_maker_families = frozenset(extra_maker_families or ()) | flag_makers
```

sha256 before the neutralization(s) in force at restore time:
```
8710b67ce064620cce47ddb1d92761dbc43d157d23a789788969f62c06db1a4d  seat_map.py
44502d22a72dda6a7d3828ecd4661d1987e423e4fb6b6870c5b54dfcbb554c9f  conformance_probe.py
```
sha256 after the restore (identical):
```
8710b67ce064620cce47ddb1d92761dbc43d157d23a789788969f62c06db1a4d  seat_map.py
44502d22a72dda6a7d3828ecd4661d1987e423e4fb6b6870c5b54dfcbb554c9f  conformance_probe.py
```

**raw green** (after restore):
```
.                                                                        [100%]
1 passed in 0.11s
green exit: 0
```

---

## N9 — conformance probe parks on `seat-unfilled` (`conformance_probe.py` `preflight_entry`)

- **axis:** a composed map with an unfilled seat parks the full lane

**neutralization** (`plugins/superheroes/lib/conformance_probe.py`):
```diff
--- before (restored text)
    if unfilled:
+++ neutralized
    if False and unfilled:
```

**command:**
```
python3 -B -m pytest plugins/superheroes/lib/tests/test_conformance_probe.py::test_e7_preflight_entry_parks_on_a_real_unfilled_seat -q -p no:cacheprovider
```

**note:** Captured with the N8 neutralization still applied (see N8).

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_e7_preflight_entry_parks_on_a_real_unfilled_seat _____________

tmp_path = PosixPath('<tmp>/pytest-N/test_e7_preflight_entry_parks_0')

    def test_e7_preflight_entry_parks_on_a_real_unfilled_seat(tmp_path):
        # codex is the implementer and the only vendor left live: nothing outside the maker's family
        # can fill a seat, so the composed map records them unfilled and the full lane parks
        repo = _repo(tmp_path)
        cal = _calibration_rows(implementation="codex", reviewer="codex", pilot="cursor")
        claude_fail = _failed_probe_result("claude", "resultProduction", repo=repo)
        cursor_fail = _failed_probe_result("cursor", "resultProduction", repo=repo)
        paths = _ok_dispatchable_probe_paths(tmp_path, repo, claude=claude_fail, cursor=cursor_fail)
        payload, code = CP.preflight_entry(
            repo,
            paths,
            launch_without=["claude", "cursor"],
            owner_words=["proceed anyway", "proceed anyway"],
            calibration_rows=cal,
        )
        assert code == 0
>       assert payload["engine-auth"]["state"] == "fail"
E       AssertionError: assert 'pass' == 'fail'
E         
E         - fail
E         + pass

<repo>/plugins/superheroes/lib/tests/test_conformance_probe.py:1132: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_conformance_probe.py::test_e7_preflight_entry_parks_on_a_real_unfilled_seat
1 failed in 0.15s
red exit: 1
```

**restore:** the inverse text swap of the neutralization above (the "before" text put back; no `git checkout`, `git restore`, `git reset` or `git stash`).

**restore receipt** (restored text as it stands in `plugins/superheroes/lib/conformance_probe.py`):
```
    if unfilled:
```

sha256 before the neutralization(s) in force at restore time:
```
8710b67ce064620cce47ddb1d92761dbc43d157d23a789788969f62c06db1a4d  seat_map.py
44502d22a72dda6a7d3828ecd4661d1987e423e4fb6b6870c5b54dfcbb554c9f  conformance_probe.py
```
sha256 after the restore (identical):
```
8710b67ce064620cce47ddb1d92761dbc43d157d23a789788969f62c06db1a4d  seat_map.py
44502d22a72dda6a7d3828ecd4661d1987e423e4fb6b6870c5b54dfcbb554c9f  conformance_probe.py
```

**raw green** (after restore):
```
.                                                                        [100%]
1 passed in 0.11s
green exit: 0
```
