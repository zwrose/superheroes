"""#1797 WO-B — verifiers, gap sweep and scoped finder sit outside every maker family.

Bite-proof record: plugins/superheroes/lib/tests/bite_proofs/wo_b_1797_seat_orders.md
"""
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import receipt_disclosures as RDS  # noqa: E402
import round_adapters as RA  # noqa: E402
import round_driver as RD  # noqa: E402
import round_records as RR  # noqa: E402
import test_round_driver_integration as TRI  # noqa: E402

NONPANEL = (RD.P_VERIFIERS, RD.P_GAPSWEEP, RD.P_SCOPED)


# --- the selection helper -----------------------------------------------------------------------

def test_independent_reviewer_bars_maker_families():
    # axis: the barred-family check on the candidate's reviewer family — see bite-proof record
    # wo_b_1797_seat_orders
    cfg = {"vendors": ["claude", "codex"]}
    # the preferred vendor stands when its family is not a maker's
    assert RDS.independent_reviewer(cfg, "codex", frozenset({"anthropic"}), None) == ("codex", "openai")
    # a preferred vendor in a maker family is replaced by the first live vendor outside them
    assert RDS.independent_reviewer(cfg, "claude", frozenset({"anthropic"}), None) == ("codex", "openai")
    # every live vendor in a maker family -> unseatable
    assert RDS.independent_reviewer(cfg, "claude", frozenset({"anthropic", "openai"}), None) == (None, None)
    assert RDS.independent_reviewer({"vendors": ["claude"]}, "claude",
                                    frozenset({"anthropic"}), None) == (None, None)


def test_independent_reviewer_adds_the_fixers_family_to_the_makers():
    cfg = {"vendors": ["claude", "codex"]}
    assert RDS.independent_reviewer(cfg, "claude", frozenset(), "claude") == ("codex", "openai")
    assert RDS.independent_reviewer(cfg, "codex", frozenset(), "codex") == ("claude", "anthropic")
    assert RDS.independent_reviewer({"vendors": ["codex"]}, "codex", frozenset(), "codex") == (None, None)


def test_independent_reviewer_never_treats_an_unresolvable_family_as_independent():
    assert RDS.independent_reviewer({"vendors": ["nope"]}, "nope", frozenset({"anthropic"}), None) == (None, None)
    assert RDS.independent_reviewer({"vendors": ["nope", "codex"]}, "nope",
                                    frozenset({"anthropic"}), None) == ("codex", "openai")
    # a non-string preferred vendor is skipped, never trusted; the live set decides
    assert RDS.independent_reviewer({"vendors": ["claude"]}, 7, frozenset({"openai"}), None) == ("claude", "anthropic")


# --- the transport chokepoint -------------------------------------------------------------------

def _state(**cfg):
    return {"config": cfg, "rounds": {}, "seatMapReceipts": []}


@pytest.mark.parametrize("phase", NONPANEL)
def test_no_makers_and_no_fixer_keeps_the_reviewer_engine_exactly(monkeypatch, phase):
    monkeypatch.setattr(RD, "_reviewer_engine_vendor", lambda root: ("claude", RD.VENDOR_SOURCE_DEFAULTED))
    row = RD._seat_transport_row(_state(vendors=["claude"]), phase, "seat", 0,
                                 {"vendors": ["claude"]}, {}, "/repo")
    assert row["vendor"] == "claude" and row["vendorSource"] == RD.VENDOR_SOURCE_DEFAULTED


@pytest.mark.parametrize("phase", NONPANEL)
def test_reviewer_engine_in_a_maker_family_is_replaced_and_marked_independent(monkeypatch, phase):
    monkeypatch.setattr(RD, "_reviewer_engine_vendor", lambda root: ("claude", RD.VENDOR_SOURCE_CONFIGURED))
    cfg = {"vendors": ["claude", "codex"], "fixerVendor": "claude"}
    row = RD._seat_transport_row(_state(**cfg), phase, "seat", 0, cfg, {}, "/repo")
    assert row["vendor"] == "codex" and row["vendorSource"] == RD.VENDOR_SOURCE_INDEPENDENT
    assert RD._vendor_is_resolved(row)
    # a reviewer engine already outside the makers stays, with its own source
    monkeypatch.setattr(RD, "_reviewer_engine_vendor", lambda root: ("codex", RD.VENDOR_SOURCE_CONFIGURED))
    row = RD._seat_transport_row(_state(**cfg), phase, "seat", 0, cfg, {}, "/repo")
    assert row["vendor"] == "codex" and row["vendorSource"] == RD.VENDOR_SOURCE_CONFIGURED


@pytest.mark.parametrize("phase", NONPANEL)
def test_a_configured_reviewer_vendor_replaced_by_b5_is_independent_and_resolved(monkeypatch, phase):
    # axis: `independent` only when the preference read answered (configured) and B5 replaced the
    # vendor; a defaulted vendor stays `defaulted` (disclosed, stdout) — see bite-proof record
    # wo_b_1797_seat_orders
    cfg = {"vendors": ["claude", "codex"], "fixerVendor": "claude"}
    monkeypatch.setattr(RD, "_reviewer_engine_vendor", lambda root: ("claude", RD.VENDOR_SOURCE_CONFIGURED))
    row = RD._seat_transport_row(_state(**cfg), phase, "seat", 0, cfg, {}, "/repo")
    assert row["vendor"] == "codex" and row["vendorSource"] == RD.VENDOR_SOURCE_INDEPENDENT
    assert RD._vendor_is_resolved(row)
    # the defaulted twin: replaced, yet still defaulted and still unresolved
    monkeypatch.setattr(RD, "_reviewer_engine_vendor", lambda root: ("claude", RD.VENDOR_SOURCE_DEFAULTED))
    row = RD._seat_transport_row(_state(**cfg), phase, "seat", 0, cfg, {}, "/repo")
    assert row["vendor"] == "codex" and row["vendorSource"] == RD.VENDOR_SOURCE_DEFAULTED
    assert not RD._vendor_is_resolved(row)


@pytest.mark.parametrize("phase", NONPANEL)
def test_every_live_vendor_in_a_maker_family_leaves_the_seat_unseatable(monkeypatch, phase):
    monkeypatch.setattr(RD, "_reviewer_engine_vendor", lambda root: ("claude", RD.VENDOR_SOURCE_CONFIGURED))
    cfg = {"vendors": ["claude"], "fixerVendor": "claude"}
    row = RD._seat_transport_row(_state(**cfg), phase, "seat", 0, cfg, {}, "/repo")
    assert row["vendor"] is None


# --- emission: the unseatable seat gets no order, a seat-missing record instead -----------------

def test_unseatable_nonpanel_seat_gets_no_order_and_a_missing_record(tmp_path):
    # axis: the unseatable non-panel seat getting NO order — see bite-proof record
    # wo_b_1797_seat_orders
    session_dir, gitdir, head_path = TRI._bootstrap(
        tmp_path, name="b5-unseatable", vendors=["claude"], fixerVendor="claude")
    TRI._drive_to_phase(session_dir, gitdir, [TRI._blocking_finding("bounds A", 2)], head_path,
                        RD.P_VERIFIERS)
    state = TRI._state(session_dir)
    pend = state["pending"]
    assert pend["phase"] == RD.P_VERIFIERS
    roster, reason = RA.roster_for(pend["phase"], state, state.get("config") or {})
    assert reason is None and roster
    manifest_path = RD._orders_manifest_path(session_dir, pend["round"], pend["phase"], pend["attempt"])
    with open(manifest_path, encoding="utf-8") as fh:
        manifest = json.load(fh)
    assert manifest["seats"] == {}
    for seat, occurrence in RR.roster_slots(roster):
        spath = RR.store_path(session_dir, pend["round"], pend["phase"],
                              RR.storage_key(seat, occurrence), pend["attempt"])
        with open(spath, encoding="utf-8") as fh:
            record = json.load(fh)
        assert record["schema"] == RR.SEAT_MISSING_SCHEMA
        assert record["reason"] == RD.UNFILLED_SEAT_REASON
        assert record["evidence"] == "no reviewer outside the makers' families is available for this seat"
        assert record["orderSha256"] == RR.NOT_EMITTED
        assert not os.path.exists(RR.order_prompt_path(
            session_dir, pend["round"], pend["phase"], RR.storage_key(seat, occurrence),
            pend["attempt"]))
