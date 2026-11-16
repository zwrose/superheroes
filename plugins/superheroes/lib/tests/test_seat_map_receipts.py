"""Tests for ``seat_map_receipts`` — the leaf projection module (#681)."""
import ast
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_HERE, "..")
_MOD = os.path.join(_LIB, "seat_map_receipts.py")

if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import liveness_cache
import round_driver as RD
import seat_map
import seat_map_receipts as SMR

_FORBIDDEN_UPWARD_IMPORTS = frozenset({
    "round_driver",
    "round_adapters",
    "round_orders",
    "round_records",
    "round_phases",
})


def _minimal_map(seats=None, **extra):
    map_ = {"seats": seats if seats is not None else {"a": {"vendor": "codex"}}}
    map_.update(extra)
    return map_


def test_seat_map_receipts_never_imports_upward_modules():
    """AST guard: leaf module must not import any upward layer (#681)."""
    with open(_MOD, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=_MOD)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name not in _FORBIDDEN_UPWARD_IMPORTS
        elif isinstance(node, ast.ImportFrom):
            if node.module in _FORBIDDEN_UPWARD_IMPORTS:
                raise AssertionError("forbidden import from %r" % node.module)


def test_emit_receipt_seat_map_violations_union_survives_clean_round():
    """axis: round-1 violations survive a round-2 receipt with an empty violations list."""
    breach = {"constraint": "maker-family", "seat": "test-role", "reason": "round-1 breach"}
    map1 = _minimal_map(violations=[breach])
    map2 = _minimal_map(violations=[])
    state = {
        "seatMapReceipts": [
            {"round": "1", "map": map1},
            {"round": "2", "map": map2},
        ],
        "rounds": {},
    }
    emitted = SMR.emit_receipt_seat_map(state)
    assert breach in emitted.get("violations", [])


def test_emit_receipt_seat_map_live_cells_source_conservative():
    """axis: disagreeing liveCellsSource resolves to the least-trusted source, not the latest."""
    map1 = _minimal_map(liveCellsSource=liveness_cache.LIVE_CELLS_SOURCE_SYNTHESIZED)
    map2 = _minimal_map(liveCellsSource=liveness_cache.LIVE_CELLS_SOURCE_PROBED)
    state = {
        "seatMapReceipts": [
            {"round": "1", "map": map1},
            {"round": "2", "map": map2},
        ],
        "rounds": {},
    }
    emitted = SMR.emit_receipt_seat_map(state)
    assert emitted.get("liveCellsSource") == liveness_cache.LIVE_CELLS_SOURCE_SYNTHESIZED


def test_emit_receipt_seat_map_zero_receipts():
    assert SMR.emit_receipt_seat_map({"rounds": {}}) == {}


def test_emit_receipt_seat_map_single_receipt_identity():
    breach = {"constraint": "maker-family", "seat": "a", "reason": "once"}
    map_ = _minimal_map(
        violations=[breach],
        liveCellsSource=liveness_cache.LIVE_CELLS_SOURCE_PROBED,
        livenessPinScoped=False,
        authorFamily="anthropic",
    )
    state = {
        "seatMapReceipts": [{"round": "1", "map": map_}],
        "rounds": {},
    }
    emitted = SMR.emit_receipt_seat_map(state, "anthropic")
    assert breach in emitted.get("violations", [])
    assert emitted["liveCellsSource"] == liveness_cache.LIVE_CELLS_SOURCE_PROBED
    assert emitted["livenessPinScoped"] is False
    assert emitted["authorFamily"] == "anthropic"


def test_effective_seat_map_prefers_latest_receipt_with_seats():
    receipt_map = _minimal_map(seats={"receipt": {"vendor": "codex"}})
    state = {
        "seatMapReceipts": [{"round": "1", "map": receipt_map}],
        "config": {"seatMap": _minimal_map(seats={"config": {"vendor": "claude"}})},
        "rounds": {},
    }
    assert SMR.effective_seat_map(state) == receipt_map


def test_effective_seat_map_falls_back_to_config_seat_map():
    config_map = _minimal_map(seats={"config": {"vendor": "claude"}})
    state = {
        "seatMapReceipts": [{"round": "1", "map": {"seats": {}}}],
        "config": {"seatMap": config_map},
        "rounds": {},
    }
    assert SMR.effective_seat_map(state) == config_map


def test_effective_seat_map_returns_empty_when_neither_present():
    state = {"seatMapReceipts": [], "config": {}, "rounds": {}}
    assert SMR.effective_seat_map(state) == {}


def test_effective_seat_map_prefers_receipt_over_config_when_both_present():
    receipt_map = _minimal_map(seats={"receipt": {"vendor": "codex"}})
    config_map = _minimal_map(seats={"config": {"vendor": "claude"}})
    state = {
        "seatMapReceipts": [{"round": "1", "map": receipt_map}],
        "config": {"seatMap": config_map},
        "rounds": {},
    }
    assert SMR.effective_seat_map(state) == receipt_map


def test_emit_receipt_seat_map_non_list_violations_do_not_erase():
    """axis: malformed violations on one receipt do not erase another receipt's list."""
    breach = {"constraint": "maker-family", "seat": "a", "reason": "kept"}
    map1 = _minimal_map(violations=[breach])
    map2 = _minimal_map(violations="not-a-list")
    state = {
        "seatMapReceipts": [
            {"round": "1", "map": map1},
            {"round": "2", "map": map2},
        ],
        "rounds": {},
    }
    emitted = SMR.emit_receipt_seat_map(state)
    assert breach in emitted.get("violations", [])


def _inv17_two_round_fixture():
    """Round 1 submitted pin-excusable strong-tier; round 2 omits violations and re-derives."""
    built = seat_map.build(
        seat_map.PANEL_ROSTER, ["codex", "cursor"], "anthropic", 0,
    )
    map1 = seat_map.to_receipt(built, "anthropic")
    map1["seats"] = dict(map1["seats"])
    map1["seats"]["security-reviewer"] = {
        "vendor": "claude",
        "model": "sonnet-5.5",
        "effort": "high",
        "tier": "reviewer",
        "family": "anthropic",
        "source": "pinned",
    }
    map1["violations"] = [{"constraint": "strong-tier", "seat": "security-reviewer"}]
    map1["livenessPinScoped"] = False
    map2 = dict(map1)
    map2["seats"] = dict(map1["seats"])
    map2.pop("violations", None)
    return map1, map2


def test_emit_receipt_seat_map_inv17_conservative_violation_merge():
    """INV-17: derived violation wins over earlier submitted pin-excusable record."""
    map1, map2 = _inv17_two_round_fixture()
    state = {
        "seatMapReceipts": [
            {"round": "1", "map": map1},
            {"round": "2", "map": map2},
        ],
        "rounds": {},
    }
    driver_fam = "anthropic"
    emitted = SMR.emit_receipt_seat_map(state, driver_fam)
    strong = [
        v for v in emitted.get("violations", [])
        if v.get("constraint") == "strong-tier" and v.get("seat") == "security-reviewer"
    ]
    assert len(strong) == 1
    assert strong[0].get("derived") is True
    classified = seat_map.classify_violations(emitted, driver_fam)
    assert strong[0] in classified["unexcused"]
    assert not any(
        r.get("constraint") == "strong-tier" and r.get("seat") == "security-reviewer"
        for r in classified.get("excusedByPin") or []
    )


def test_unjudgeable_receipts_quantifier_both_orders():
    """INV-9 receipts-only: any unjudgeable receipt arms — not first-wins or last-wins."""
    judgeable = _minimal_map(authorFamily="anthropic")
    unjudgeable = _minimal_map(seats={})
    orderings = [
        [{"round": "1", "map": judgeable}, {"round": "2", "map": unjudgeable}],
        [{"round": "1", "map": unjudgeable}, {"round": "2", "map": judgeable}],
    ]
    cfg = {"leg": "panel", "vendors": ["codex", "cursor"], "fixerVendor": "claude"}
    driver_fam = RD._driver_author_family(RD.new_state(cfg))
    for receipts in orderings:
        state = RD.new_state(cfg)
        state["seatMapReceipts"] = receipts
        state["rounds"] = {}
        unj = SMR.unjudgeable_receipts(state, driver_fam)
        assert len(unj) == 1
        assert unj[0]["basis"] == seat_map.VIOLATION_BASIS_NO_SEATS
        assert RD._seat_map_unjudgeable(state) is True


def test_round_governing_unjudgeable_seeded_round_zero_receipt():
    """Selector: round ``0`` seeded receipt is judged on its own submission."""
    judgeable = _minimal_map(authorFamily="anthropic")
    state = {
        "seatMapReceipts": [{"round": "0", "map": judgeable}],
        "config": {"seatMap": _minimal_map(seats={})},
        "rounds": {},
    }
    driver_fam = "anthropic"
    assert SMR.round_governing_unjudgeable(state, "0", driver_fam) == []
    unjudgeable = _minimal_map(seats={})
    state["seatMapReceipts"] = [{"round": "0", "map": unjudgeable}]
    result = SMR.round_governing_unjudgeable(state, "0", driver_fam)
    assert result == [{"round": "0", "basis": seat_map.VIOLATION_BASIS_NO_SEATS}]


def test_round_governing_unjudgeable_legacy_prepend_then_empty_seats_receipt():
    """Selector: legacy ``state["seatMap"]`` prepend does not mask the round's own submission."""
    judgeable = _minimal_map(authorFamily="anthropic")
    unjudgeable = _minimal_map(seats={})
    state = {
        "seatMap": judgeable,
        "seatMapReceipts": [{"round": "1", "map": unjudgeable}],
        "rounds": {},
    }
    driver_fam = "anthropic"
    assert SMR.round_governing_unjudgeable(state, "1", driver_fam) == [
        {"round": "1", "basis": seat_map.VIOLATION_BASIS_NO_SEATS},
    ]


def test_round_governing_unjudgeable_config_fallback_without_receipts():
    """Selector: ``config["seatMap"]`` fallback when the round submitted no map."""
    config_map = _minimal_map(authorFamily="anthropic")
    state = {"config": {"seatMap": config_map}, "rounds": {}}
    driver_fam = "anthropic"
    assert SMR.round_governing_unjudgeable(state, "2", driver_fam) == []
    bad_config = _minimal_map(seats={})
    state["config"]["seatMap"] = bad_config
    assert SMR.round_governing_unjudgeable(state, "2", driver_fam) == [
        {"round": "2", "basis": seat_map.VIOLATION_BASIS_NO_SEATS},
    ]


def test_round_governing_unjudgeable_last_receipt_wins_same_round_label():
    """Selector: list order decides last receipt for a round label — not numeric sort."""
    first = _minimal_map(authorFamily="anthropic")
    second = _minimal_map(seats={})
    state = {
        "seatMapReceipts": [
            {"round": "10", "map": first},
            {"round": "2", "map": second},
            {"round": "10", "map": second},
        ],
        "rounds": {},
    }
    driver_fam = "anthropic"
    assert SMR.round_governing_unjudgeable(state, "10", driver_fam) == [
        {"round": "10", "basis": seat_map.VIOLATION_BASIS_NO_SEATS},
    ]


def test_round_governing_unjudgeable_return_shape_complete_vs_one_element():
    """Selector: ``[]`` when complete; one-element list with round and basis otherwise."""
    complete = _minimal_map(authorFamily="anthropic")
    incomplete = _minimal_map(seats={})
    state = {
        "seatMapReceipts": [{"round": "3", "map": complete}],
        "rounds": {},
    }
    driver_fam = "anthropic"
    assert SMR.round_governing_unjudgeable(state, "3", driver_fam) == []
    state["seatMapReceipts"] = [{"round": "3", "map": incomplete}]
    result = SMR.round_governing_unjudgeable(state, "3", driver_fam)
    assert len(result) == 1
    assert result[0]["round"] == "3"
    assert result[0]["basis"] == seat_map.VIOLATION_BASIS_NO_SEATS


def test_round_governing_unjudgeable_own_submission_wins_over_effective_map():
    """Selector: own submission wins — not ``effective_seat_map`` when the round submitted."""
    judgeable = _minimal_map(authorFamily="anthropic")
    unjudgeable = _minimal_map(seats={})
    state = {
        "seatMapReceipts": [
            {"round": "1", "map": unjudgeable},
            {"round": "2", "map": judgeable},
        ],
        "rounds": {},
    }
    driver_fam = "anthropic"
    assert SMR.round_governing_unjudgeable(state, "2", driver_fam) == []
    state["seatMapReceipts"] = [
        {"round": "1", "map": judgeable},
        {"round": "2", "map": unjudgeable},
    ]
    assert SMR.round_governing_unjudgeable(state, "2", driver_fam) == [
        {"round": "2", "basis": seat_map.VIOLATION_BASIS_NO_SEATS},
    ]


def test_unjudgeable_receipts_whole_history_not_round_scoped():
    """Whole-history reader still returns every unjudgeable receipt across rounds (#1204)."""
    judgeable = _minimal_map(authorFamily="anthropic")
    unjudgeable = _minimal_map(seats={})
    state = {
        "seatMapReceipts": [
            {"round": "1", "map": unjudgeable},
            {"round": "2", "map": judgeable},
            {"round": "3", "map": unjudgeable},
        ],
        "rounds": {},
    }
    driver_fam = "anthropic"
    result = SMR.unjudgeable_receipts(state, driver_fam)
    assert len(result) == 2
    assert result[0] == {"round": "1", "basis": seat_map.VIOLATION_BASIS_NO_SEATS}
    assert result[1] == {"round": "3", "basis": seat_map.VIOLATION_BASIS_NO_SEATS}
    assert SMR.round_governing_unjudgeable(state, "2", driver_fam) == []


def test_emit_receipt_seat_map_merges_maker_families_and_roster():
    """axis: makerFamilies is the sorted union over every receipt; roster is last-wins."""
    roster_1 = ["code-reviewer", "test-role"]
    roster_2 = ["code-reviewer", "premortem-reviewer"]
    map1 = _minimal_map(makerFamilies=["anthropic"], roster=roster_1)
    map2 = _minimal_map(makerFamilies=["openai", "anthropic"], roster=roster_2)
    state = {
        "seatMapReceipts": [
            {"round": "1", "map": map1},
            {"round": "2", "map": map2},
            {"round": "3", "map": _minimal_map(makerFamilies=["xai"])},
        ],
        "rounds": {},
    }
    emitted = SMR.emit_receipt_seat_map(state)
    assert emitted["makerFamilies"] == ["anthropic", "openai", "xai"]
    assert emitted["roster"] == roster_2


def test_emit_receipt_seat_map_carries_what_a_composed_receipt_names():
    built = seat_map.build(seat_map.PANEL_ROSTER, ["claude", "codex"], "anthropic", 0,
                           extra_maker_families=frozenset({"xai"}))
    receipt = seat_map.to_receipt(built, "anthropic")
    assert receipt["makerFamilies"] == ["anthropic", "xai"]
    assert receipt["roster"] == list(seat_map.PANEL_ROSTER)
    emitted = SMR.emit_receipt_seat_map({"seatMapReceipts": [{"round": "1", "map": receipt}]})
    assert emitted["makerFamilies"] == ["anthropic", "xai"]
    assert emitted["roster"] == list(seat_map.PANEL_ROSTER)


def test_emit_receipt_seat_map_without_the_keys_invents_none():
    emitted = SMR.emit_receipt_seat_map({"seatMapReceipts": [{"round": "1", "map": _minimal_map()}]})
    assert "makerFamilies" not in emitted
    assert "roster" not in emitted


def test_emit_receipt_seat_map_keeps_a_legacy_author_family_as_a_maker():
    """axis: a legacy map naming its maker only through authorFamily keeps it in the emitted makerFamilies."""
    state = {"seatMapReceipts": [{"round": "1", "map": _minimal_map(authorFamily="openai")},
                                 {"round": "2", "map": _minimal_map(authorFamily="anthropic", makerFamilies=["anthropic"])}],
             "rounds": {}}
    assert SMR.emit_receipt_seat_map(state)["makerFamilies"] == ["anthropic", "openai"]


# --- a panel outside every maker's family is not a critical-diversity breach (#2530) -------------

_CRITICAL_DIVERSITY_ROW = {
    "constraint": "critical-diversity",
    "reason": "relaxed critical-diversity — no assignment spanned ≥2 families",
}


def _stored_outside_makers_map():
    """A map stored before #2530: every critical seat pinned to codex, no maker seated, a
    `critical-diversity` violation and degradation submitted with it."""
    pins = {seat: {"vendor": "codex"} for seat in sorted(seat_map.CRITICAL_SEATS)}
    built = seat_map.build(seat_map.PANEL_ROSTER, ["codex"], "anthropic", 0, pins=pins)
    stored = seat_map.to_receipt(built, "anthropic")
    stored["violations"] = [{"constraint": "critical-diversity"}]
    stored["degradations"] = [
        d for d in stored["degradations"] if d.get("constraint") != "critical-diversity"
    ] + [dict(_CRITICAL_DIVERSITY_ROW)]
    stored["livenessPinScoped"] = False
    return stored


def _without_critical_diversity(m):
    return [d for d in m["degradations"] if d.get("constraint") != "critical-diversity"]


def _has_critical_diversity(rows):
    return any(isinstance(r, dict) and r.get("constraint") == "critical-diversity" for r in rows or [])


def _emit(maps, driver_author_family=None):
    state = {"seatMapReceipts": [{"round": str(i + 1), "map": m} for i, m in enumerate(maps)], "rounds": {}}
    return SMR.emit_receipt_seat_map(state, driver_author_family)


def test_emit_receipt_seat_map_drops_a_critical_diversity_row_for_a_panel_outside_the_makers():
    # axis: a receipt's critical-diversity degradation is not emitted for a panel outside every maker's family — see bite-proof record wo_a_2530_single_vendor_panel
    stored = _stored_outside_makers_map()
    other = {"constraint": "pin", "reason": "pin for unknown seat nope"}
    stored["degradations"] = stored["degradations"] + [other]
    for driver in (None, "anthropic"):
        emitted = _emit([stored], driver)
        assert not _has_critical_diversity(emitted["degradations"]), driver
        assert other in emitted["degradations"], driver
    # when the dropped row was the only one, the map's own copy of it must not come through instead
    only = dict(stored, degradations=[dict(_CRITICAL_DIVERSITY_ROW)])
    for driver in (None, "anthropic"):
        assert not _has_critical_diversity(_emit([only], driver).get("degradations")), driver


def test_emit_receipt_seat_map_keeps_a_critical_diversity_row_when_a_maker_is_seated():
    stored = _stored_outside_makers_map()
    seated = dict(stored, seats=dict(stored["seats"]))
    seated["seats"]["security-reviewer"] = dict(stored["seats"]["security-reviewer"], vendor="claude")
    assert not seat_map.panel_outside_makers(seated, "anthropic")
    assert _CRITICAL_DIVERSITY_ROW in _emit([seated], "anthropic")["degradations"]
    # judged per receipt, with DISTINCT rows so the assertion tells the two receipts apart (FU2): the
    # outside-round receipt (every seat codex) drops its row, the maker-round receipt (one seat on the
    # author's own family, anthropic) keeps its row — in either order. The maker the second receipt names is
    # the author's own family, so the session's maker set stays {anthropic} and the first receipt's codex
    # seats stay outside every maker the session names.
    outside_row = {"constraint": "critical-diversity", "reason": "outside-round"}
    maker_row = {"constraint": "critical-diversity", "reason": "maker-round"}
    outside_receipt = dict(stored, degradations=_without_critical_diversity(stored) + [dict(outside_row)])
    maker_receipt = dict(seated, degradations=_without_critical_diversity(seated) + [dict(maker_row)])
    assert seat_map.panel_outside_makers(outside_receipt, "anthropic")
    assert not seat_map.panel_outside_makers(maker_receipt, "anthropic")
    for order in ((outside_receipt, maker_receipt), (maker_receipt, outside_receipt)):
        emitted = _emit(list(order), "anthropic")
        assert outside_row not in emitted["degradations"], [m["degradations"][-1]["reason"] for m in order]
        assert emitted["degradations"].count(maker_row) == 1, [m["degradations"][-1]["reason"] for m in order]
    # an unknown author family keeps the row too
    no_author = {k: v for k, v in stored.items() if k != "authorFamily"}
    assert _CRITICAL_DIVERSITY_ROW in _emit([no_author])["degradations"]


def test_critical_diversity_never_appears_for_a_panel_outside_every_maker():
    # census of the chokepoint (#2530): a seat map that meets the predicate yields no critical-diversity
    # record from derived_violations, any classify_violations bucket, a build, or the emitted receipt
    fresh_claude = seat_map.build(seat_map.PANEL_ROSTER, ["claude"], "xai", 0)
    fresh_codex = seat_map.build(seat_map.PANEL_ROSTER, ["claude", "codex"], "anthropic", 0)
    legacy = _stored_outside_makers_map()
    maps = {
        "fresh claude-only build": (fresh_claude, "xai"),
        "fresh codex-only build": (fresh_codex, "anthropic"),
        "to_receipt of a fresh build": (seat_map.to_receipt(fresh_claude, "xai"), "xai"),
        "legacy stored record": (legacy, "anthropic"),
        "legacy with an extra maker nobody is seated in": (dict(legacy, makerFamilies=["anthropic", "google"]), "anthropic"),
    }
    for label, (m, author) in maps.items():
        assert seat_map.panel_outside_makers(m, author), label
        assert not _has_critical_diversity(seat_map.verify(m, author)), label
        assert not _has_critical_diversity(seat_map.derived_violations(m, author)), label
        classified = seat_map.classify_violations(m, author)
        for bucket in ("unexcused", "excusedByPin", "excusedByLiveness"):
            assert not _has_critical_diversity(classified[bucket]), (label, bucket)
        state = {"seatMapReceipts": [{"round": "1", "map": m}], "rounds": {}}
        assert not _has_critical_diversity(SMR.unexcused_violations(state, author)), label
        assert not _has_critical_diversity(SMR.pin_excused_records(state, author)), label
        emitted = SMR.emit_receipt_seat_map(state, author)
        assert not _has_critical_diversity(emitted.get("violations")), label
        assert not _has_critical_diversity(emitted.get("degradations")), label
        if "build" in label:
            assert not _has_critical_diversity(m["degradations"]), label


# --- the exemption reads the session's whole maker set (#2530, WO-C) ----------------------------


def _session_state(maps, former_fixer_families=None):
    state = {"seatMapReceipts": [{"round": str(i + 1), "map": m} for i, m in enumerate(maps)], "rounds": {}}
    if former_fixer_families is not None:
        state["formerFixerFamilies"] = former_fixer_families
    return state


def _unpinned_all_codex_map():
    """An all-codex map with no submitted violation: a maker (openai) in the session makes its
    `critical-diversity` DERIVED, and a derived record is never excused."""
    built = seat_map.build(seat_map.PANEL_ROSTER, ["codex"], "anthropic", 0)
    return seat_map.to_receipt(built, "anthropic")


def test_state_level_unexcused_violations_read_the_sessions_former_fixer_family():
    # axis: the state-level unexcused projection judges a map against the session's whole maker set — see bite-proof record wo_a_2530_single_vendor_panel
    m = _unpinned_all_codex_map()
    assert seat_map.panel_outside_makers(m, "anthropic")
    assert not _has_critical_diversity(SMR.unexcused_violations(_session_state([m]), "anthropic"))
    # an openai fixer a session upgrade replaced is still a maker: the all-codex panel is in its family
    state = _session_state([m], former_fixer_families=["openai"])
    unexcused = SMR.unexcused_violations(state, "anthropic")
    assert _has_critical_diversity(unexcused)
    assert all(v.get("derived") is True for v in unexcused if v.get("constraint") == "critical-diversity")
    # shape (a): a later receipt that omits openai does not release it
    earlier = dict(m, makerFamilies=["anthropic", "openai"], seats={})
    assert _has_critical_diversity(SMR.unexcused_violations(_session_state([earlier, m]), "anthropic"))


def test_state_level_pin_excused_records_read_the_sessions_makers():
    stored = _stored_outside_makers_map()
    assert not _has_critical_diversity(SMR.pin_excused_records(_session_state([stored]), "anthropic"))
    for state in (
        _session_state([stored], former_fixer_families=["openai"]),
        _session_state([dict(stored, makerFamilies=["anthropic", "openai"]), stored]),
    ):
        assert _has_critical_diversity(SMR.pin_excused_records(state, "anthropic"))
        assert not _has_critical_diversity(SMR.unexcused_violations(state, "anthropic"))


def test_emit_receipt_seat_map_keeps_the_critical_diversity_row_when_a_former_fixer_is_a_maker():
    # axis: the emitted seat map judges each receipt against the session's whole maker set — see bite-proof record wo_a_2530_single_vendor_panel
    stored = _stored_outside_makers_map()
    healthy = SMR.emit_receipt_seat_map(_session_state([stored]), "anthropic")
    assert not _has_critical_diversity(healthy.get("degradations"))
    assert not _has_critical_diversity(healthy.get("violations"))
    for state in (
        _session_state([stored], former_fixer_families=["openai"]),
        _session_state([dict(stored, makerFamilies=["anthropic", "openai"]), stored]),
    ):
        emitted = SMR.emit_receipt_seat_map(state, "anthropic")
        assert _CRITICAL_DIVERSITY_ROW in emitted["degradations"]
        assert _has_critical_diversity(emitted.get("violations"))
    # a malformed formerFixerFamilies names no maker (E5)
    for bad in ("openai", 7, [None, 5, ""], {"openai": 1}):
        emitted = SMR.emit_receipt_seat_map(_session_state([stored], former_fixer_families=bad), "anthropic")
        assert not _has_critical_diversity(emitted.get("degradations")), bad


def test_same_family_seats_reads_a_session_with_a_former_fixer_without_error():
    m = _unpinned_all_codex_map()
    assert SMR.same_family_seats(_session_state([m], former_fixer_families=["openai"]), "anthropic") == []


def test_importing_either_side_of_the_receipt_import_cycle_works_in_a_fresh_interpreter():
    # E6: seat_map_receipts imports receipt_disclosures lazily (receipt_disclosures imports seat_map_receipts)
    lib_dir = os.path.abspath(_LIB)
    for module in ("seat_map_receipts", "receipt_disclosures"):
        done = subprocess.run(
            [sys.executable, "-B", "-c", "import " + module], cwd=lib_dir, capture_output=True, text=True,
        )
        assert done.returncode == 0, (module, done.stderr)
