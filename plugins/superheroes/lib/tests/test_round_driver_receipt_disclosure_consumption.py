#!/usr/bin/env python3
"""#1195-A — build_receipt reads per-round disclosure channels through the shared selection rule."""
import ast
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import round_driver  # noqa: E402
import version_skew  # noqa: E402

_INVARIANT_A = (
    "Building a terminal receipt never raises on a malformed per-round disclosure channel: "
    "every read of a RESUMABLE_DISCLOSURE_CHANNELS key off a per-round entry in build_receipt "
    "must go through the shared selection rule except the verifyPasses carve-out."
)
_INVARIANT_B = (
    "Building a terminal receipt never raises on a malformed per-round disclosure channel: "
    "helper-reached channel readers must tolerate non-list values structurally."
)


def _minimal_state(round_entry=None, schema_version=3):
    state = round_driver.new_state({"leg": "code", "vendors": ["claude"]})
    state["schemaVersion"] = schema_version
    state["terminal"] = "converged"
    state["certification"] = {"shape": "audited-chain"}
    if round_entry is not None:
        state["rounds"] = {"1": round_entry}
    else:
        state["rounds"] = {}
    return state


def _round_entry(receipt):
    rounds = receipt.get("rounds") or []
    assert len(rounds) == 1
    return rounds[0]


def _degraded_prose(receipt):
    return "\n".join(receipt.get("degraded") or [])


def _skew_row(reason="plugin-version-skew: test skew line"):
    return {
        "constraint": version_skew.CONSTRAINT,
        "status": version_skew.STATUS_CHECKED_DEGRADED,
        "detail": version_skew.DETAIL_SEMANTICS_DIVERGENT,
        "reason": reason,
        "inspectedRoot": "/tmp/repo",
    }


# --- E1: shape filter live in receipt builder ---


def test_e1_malformed_vacuous_seats_dropped_by_shape_filter():
    """E1 — malformed vacuousSeats is dropped, not coerced; receipt agrees with _declared_disclosures."""
    entry = {"vacuousSeats": ["code", 7]}
    assert "vacuousSeats" not in round_driver._declared_disclosures(entry)
    state = _minimal_state(entry)
    receipt = round_driver.build_receipt(state)
    rd = _round_entry(receipt)
    assert "vacuousSeats" not in rd
    assert "vacuous-seat" not in _degraded_prose(receipt)


# --- E2: crash site + well-formed pin ---


def test_e2_malformed_vacuous_seats_no_crash_well_formed_still_discloses():
    """E2 — malformed vacuousSeats does not raise; well-formed still emits exact prose."""
    malformed = _minimal_state({"vacuousSeats": ["code", 7]})
    receipt_bad = round_driver.build_receipt(malformed)
    assert "vacuous-seat" not in _degraded_prose(receipt_bad)

    well_formed = _minimal_state({"vacuousSeats": ["code", "security"]})
    receipt_good = round_driver.build_receipt(well_formed)
    expected = (
        "vacuous-seat (round 1): seat(s) code, security returned no findings and no verifiable "
        "investigation record — classed as never-ran"
    )
    assert expected in _degraded_prose(receipt_good)


# --- E3: form gate preserved ---


def test_e3_verify_passes_form_gate_v2_omits_v3_emits():
    """E3 — verifyPasses omitted on v2 certified, present on v3 certified."""
    entry = {"verifyPasses": [{"CONFIRMED": 1}]}
    v2_state = _minimal_state(entry, schema_version=2)
    assert "verifyPasses" not in round_driver._receipt_round_disclosures(
        entry, round_driver.RECEIPT_FORM_CERTIFIED, v2_state)
    v2_receipt = round_driver.build_receipt(v2_state)
    assert "verifyPasses" not in _round_entry(v2_receipt)

    v3_state = _minimal_state(entry, schema_version=3)
    assert "verifyPasses" in round_driver._receipt_round_disclosures(
        entry, round_driver.RECEIPT_FORM_CERTIFIED, v3_state)
    v3_receipt = round_driver.build_receipt(v3_state)
    assert "verifyPasses" in _round_entry(v3_receipt)


# --- E4: verifyPasses always-emit carve-out ---


def test_e4_verify_passes_always_emit_carve_out():
    """E4 — empty round emits []; non-list coerced to [], not dropped."""
    empty_state = _minimal_state({})
    empty_receipt = round_driver.build_receipt(empty_state)
    assert _round_entry(empty_receipt)["verifyPasses"] == []

    non_list_state = _minimal_state({"verifyPasses": "not-a-list"})
    non_list_receipt = round_driver.build_receipt(non_list_state)
    assert _round_entry(non_list_receipt)["verifyPasses"] == []


# --- E5: build_receipt AST census (invariant A) ---


def _build_receipt_channel_get_reads():
    source = open(
        os.path.join(_LIB, "round_driver.py"), encoding="utf-8").read()
    tree = ast.parse(source)
    fn = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "build_receipt")
    channels = set(round_driver.RESUMABLE_DISCLOSURE_CHANNELS)
    reads = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr != "get":
            continue
        if not isinstance(func.value, ast.Name):
            continue
        if func.value.id == "declared":
            continue
        if len(node.args) != 1 or not isinstance(node.args[0], ast.Constant):
            continue
        if not isinstance(node.args[0].value, str):
            continue
        key = node.args[0].value
        if key in channels:
            reads.append(key)
    return reads


def test_e5_build_receipt_only_sanctioned_verify_passes_raw_read():
    """E5 — only verifyPasses raw .get() remains inside build_receipt."""
    reads = _build_receipt_channel_get_reads()
    assert reads == ["verifyPasses"], (
        "%s Found raw channel reads: %r" % (_INVARIANT_A, reads))


# --- E6: helper-reached readers do not crash ---


def test_e6_malformed_skew_and_violations_do_not_crash():
    """E6 — malformed pluginVersionSkew / seatMapViolations do not raise through build_receipt."""
    skew_state = _minimal_state({"pluginVersionSkew": 7})
    round_driver.build_receipt(skew_state)

    viol_state = _minimal_state({"seatMapViolations": 7})
    round_driver.build_receipt(viol_state)

    int_constraint_state = _minimal_state({
        "seatMapViolations": [{"constraint": 7, "seat": "code"}],
    })
    receipt = round_driver.build_receipt(int_constraint_state)
    breach_lines = [line for line in receipt["degraded"]
                    if line.startswith("seat-map constraint breach:")]
    assert breach_lines
    assert isinstance(breach_lines[0], str)


def test_e6_well_formed_skew_and_violations_pin_exact_prose():
    """E6 pin — well-formed skew and breach rows still produce today's exact prose."""
    skew_state = _minimal_state({"pluginVersionSkew": [_skew_row("plugin-version-skew: exact line")]})
    skew_receipt = round_driver.build_receipt(skew_state)
    assert "plugin-version-skew: exact line" in _degraded_prose(skew_receipt)

    viol_state = _minimal_state({
        "seatMapViolations": [{"constraint": "cross-vendor", "seat": "code-reviewer",
                               "evidence": "alternative-live"}],
    })
    viol_receipt = round_driver.build_receipt(viol_state)
    expected_breach = (
        "seat-map constraint breach: cross-vendor (seat code-reviewer; an alternative was "
        "available) — breach recorded; certification withheld"
    )
    assert expected_breach in _degraded_prose(viol_receipt)


# --- E7: helper census (invariant B) ---


def _helper_channel_read_is_list_guarded(fn_name, channel):
    source = open(
        os.path.join(_LIB, "round_driver.py"), encoding="utf-8").read()
    tree = ast.parse(source)
    fn = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == fn_name)
    for node in ast.walk(fn):
        if not isinstance(node, ast.For):
            continue
        iter_expr = node.iter
        if not isinstance(iter_expr, ast.Call):
            continue
        call = iter_expr
        if not isinstance(call.func, ast.Attribute) or call.func.attr != "get":
            continue
        if len(call.args) != 1:
            continue
        if not isinstance(call.args[0], ast.Constant) or call.args[0].value != channel:
            continue
        return False
    for node in ast.walk(fn):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if not isinstance(test, ast.UnaryOp) or not isinstance(test.op, ast.Not):
            continue
        call = test.operand
        if not isinstance(call, ast.Call):
            continue
        if not isinstance(call.func, ast.Name) or call.func.id != "isinstance":
            continue
        if len(call.args) != 2:
            continue
        if not isinstance(call.args[0], ast.Name):
            continue
        if not isinstance(call.args[1], ast.Name) or call.args[1].id != "list":
            continue
        var_name = call.args[0].id
        for assign in ast.walk(fn):
            if not isinstance(assign, ast.Assign):
                continue
            if len(assign.targets) != 1:
                continue
            target = assign.targets[0]
            if not isinstance(target, ast.Name) or target.id != var_name:
                continue
            value = assign.value
            if not isinstance(value, ast.Call):
                continue
            if not isinstance(value.func, ast.Attribute) or value.func.attr != "get":
                continue
            if len(value.args) != 1:
                continue
            if not isinstance(value.args[0], ast.Constant):
                continue
            if value.args[0].value == channel:
                return True
    return False


def test_e7_helper_channel_reads_guarded_by_isinstance_list():
    """E7 — _skew_records and _seat_map_violations guard channel reads with isinstance(..., list)."""
    assert _helper_channel_read_is_list_guarded("_skew_records", "pluginVersionSkew"), (
        "%s _skew_records must not iterate a bare rec.get(pluginVersionSkew) or []"
        % _INVARIANT_B)
    assert _helper_channel_read_is_list_guarded("_seat_map_violations", "seatMapViolations"), (
        "%s _seat_map_violations must not iterate a bare rec.get(seatMapViolations) or []"
        % _INVARIANT_B)


# --- canaryVerified empty-but-present pin ---


def test_empty_canary_verified_still_emits_on_certified_receipt():
    """Empty-but-present canaryVerified ({}) still emits on a certified receipt."""
    state = _minimal_state({"canaryVerified": {}})
    receipt = round_driver.build_receipt(state)
    rd = _round_entry(receipt)
    assert "canaryVerified" in rd
    assert rd["canaryVerified"] == {}
