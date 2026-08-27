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
    emitted = SMR.emit_receipt_seat_map(state)
    assert emitted["violations"] == [breach]
    assert emitted["liveCellsSource"] == liveness_cache.LIVE_CELLS_SOURCE_PROBED
    assert emitted["livenessPinScoped"] is False
    assert emitted["authorFamily"] == "anthropic"


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


def test_effective_seat_map_single_home_census():
    """Resolution has exactly one implementation — in seat_map_receipts (#681 arch-001)."""
    adapters_path = os.path.join(_LIB, "round_adapters.py")
    driver_path = os.path.join(_LIB, "round_driver.py")
    with open(_MOD, encoding="utf-8") as fh:
        receipts_source = fh.read()
    with open(adapters_path, encoding="utf-8") as fh:
        adapters_source = fh.read()
    with open(driver_path, encoding="utf-8") as fh:
        driver_source = fh.read()
    assert receipts_source.count("def effective_seat_map(") == 1
    assert driver_source.count("def effective_seat_map(") == 0
    assert adapters_source.count("def effective_seat_map(") == 0
    leaf_calls = adapters_source.count("seat_map_receipts.effective_seat_map")
    assert leaf_calls >= 1


def test_effective_seat_map_falls_back_to_config_then_empty():
    """axis: config seatMap wins when no receipt carries seats; else empty latest map."""
    cfg_map = {"seats": {"x": {"vendor": "claude"}}}
    state = {"config": {"seatMap": cfg_map}, "seatMapReceipts": []}
    assert SMR.effective_seat_map(state) == cfg_map
    empty = {"config": {}, "seatMapReceipts": [{"round": "1", "map": {"seats": {}}}]}
    assert SMR.effective_seat_map(empty) == {"seats": {}}
