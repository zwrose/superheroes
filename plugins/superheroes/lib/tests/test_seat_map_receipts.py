"""Tests for ``seat_map_receipts`` — the leaf projection module (#681)."""
import ast
import os
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
import version_skew

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


def test_unknown_skew_status_without_degradation_degrades():
    """axis: unknown pluginVersionSkew.status degrades even without an explicit degradation row."""
    state = {
        "seatMapReceipts": [{
            "round": "1",
            "map": {
                "seats": {"a": {"vendor": "codex"}},
                "pluginVersionSkew": {"status": "bogus-status"},
            },
        }],
        "rounds": {},
    }
    records = SMR.skew_records(state)
    assert len(records) == 1
    assert version_skew.appends_degradation(records[0]["status"])
    assert "bogus-status" in records[0]["reason"]
    assert RD._skew_degraded(state) is True


def test_recognized_degrading_skew_no_synthetic_duplicate():
    """axis: explicit degrading row is not duplicated by the unknown-status synthetic path."""
    row = {
        "constraint": version_skew.CONSTRAINT,
        "status": version_skew.STATUS_CHECKED_DEGRADED,
        "detail": version_skew.DETAIL_SEMANTICS_DIVERGENT,
        "reason": "explicit",
        "inspectedRoot": "/tmp/repo",
    }
    state = {
        "seatMapReceipts": [{
            "round": "1",
            "map": {
                "seats": {"a": {"vendor": "codex"}},
                "degradations": [row],
                "pluginVersionSkew": {
                    "status": version_skew.STATUS_CHECKED_DEGRADED,
                    "detail": version_skew.DETAIL_SEMANTICS_DIVERGENT,
                    "inspectedRoot": "/tmp/repo",
                },
            },
        }],
        "rounds": {},
    }
    records = SMR.skew_records(state)
    assert len(records) == 1
    assert records[0]["reason"] == "explicit"


def test_emit_receipt_seat_map_violations_union_survives_clean_round():
    """axis: round-1 violations survive a round-2 receipt with an empty violations list."""
    breach = {"constraint": "maker-family", "seat": "test-reviewer", "reason": "round-1 breach"}
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
        seat_map.PANEL_ROSTER, ["codex", "cursor"], "anthropic", "anthropic", 0,
    )
    map1 = seat_map.to_receipt(built, "anthropic")
    map1["seats"] = dict(map1["seats"])
    map1["seats"]["security-reviewer"] = {
        "vendor": "claude",
        "model": "sonnet-5",
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
