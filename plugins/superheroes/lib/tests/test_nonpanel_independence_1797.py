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


def test_independent_reviewer_bars_another_vendor_in_the_fixers_family(monkeypatch):
    real = RDS.model_registry.family_for
    # a third live vendor shares the fixer's family: only the family bar can exclude it
    monkeypatch.setattr(RDS.model_registry, "family_for",
                        lambda role, v: "anthropic" if v == "codex" else real(role, v))
    cfg = {"vendors": ["claude", "codex", "cursor"]}
    got = RDS.independent_reviewer(cfg, "codex", frozenset(), "claude")
    assert got[0] is not None and got[0] not in ("claude", "codex")


def test_independent_reviewer_never_treats_an_unresolvable_family_as_independent():
    assert RDS.independent_reviewer({"vendors": ["nope"]}, "nope", frozenset({"anthropic"}), None) == (None, None)
    assert RDS.independent_reviewer({"vendors": ["nope", "codex"]}, "nope",
                                    frozenset({"anthropic"}), None) == ("codex", "openai")
    # a non-string preferred vendor is skipped, never trusted; the live set decides
    assert RDS.independent_reviewer({"vendors": ["claude"]}, 7, frozenset({"openai"}), None) == ("claude", "anthropic")


# --- the transport chokepoint -------------------------------------------------------------------

def _state(**cfg):
    return {"config": cfg, "rounds": {}, "seatMapReceipts": []}


def _seat(vendor, family):
    return {"vendor": vendor, "family": family, "model": "m", "tier": "reviewer"}


def _maker_state(**cfg):
    # an earlier receipt names openai as a maker; a later one names only anthropic; both nonempty
    return {"config": cfg, "rounds": {}, "seatMapReceipts": [
        {"round": "1", "map": {"seats": {"code-reviewer": _seat("codex", "openai")},
                               "makerFamilies": ["openai"]}},
        {"round": "2", "map": {"seats": {"code-reviewer": _seat("claude", "anthropic")},
                               "makerFamilies": ["anthropic"]}},
    ]}


@pytest.mark.parametrize("phase", NONPANEL)
def test_an_earlier_nonfixer_maker_family_is_barred_from_the_transport_row(monkeypatch, phase):
    # axis: the driver forwards the accumulated maker families to independent_reviewer — see bite-proof record
    # wo_b_1797_seat_orders
    monkeypatch.setattr(RD, "_reviewer_engine_vendor", lambda root: ("codex", RD.VENDOR_SOURCE_CONFIGURED))
    cfg = {"vendors": ["claude", "codex", "cursor"], "fixerVendor": "claude"}
    row = RD._seat_transport_row(_maker_state(**cfg), phase, "seat", 0, cfg, {}, "/repo")
    assert row["vendor"] == "cursor" and row["vendorSource"] == RD.VENDOR_SOURCE_INDEPENDENT
    cfg = {"vendors": ["claude", "codex"], "fixerVendor": "claude"}
    row = RD._seat_transport_row(_maker_state(**cfg), phase, "seat", 0, cfg, {}, "/repo")
    assert row["vendor"] is None


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

@pytest.mark.parametrize("phase", ["P_VERIFIERS", "P_GAPSWEEP", "P_SCOPED"])
def test_unseatable_nonpanel_seat_gets_no_order_and_a_missing_record(tmp_path, phase):
    phase = getattr(RD, phase)
    # axis: the unseatable non-panel seat getting NO order — see bite-proof record
    # wo_b_1797_seat_orders
    session_dir, gitdir, head_path = TRI._bootstrap(
        tmp_path, name="b5-unseatable-" + phase, vendors=["claude"], fixerVendor="claude")
    TRI._drive_to_phase(session_dir, gitdir, [TRI._blocking_finding("bounds A", 2)], head_path,
                        RD.P_VERIFIERS)
    state = TRI._state(session_dir)
    pend = dict(state["pending"])
    if phase != RD.P_VERIFIERS:
        # An unseatable session never advances past verifiers, so emit the later phase's orders
        # directly from the same state: the guard under test is the emission one.
        pend["phase"] = phase
        roster, reason = RA.roster_for(phase, state, state.get("config") or {})
        assert reason is None and roster
        RD._emit_orders_manifest(session_dir, state, pend["round"], phase, pend["attempt"], roster,
                                 pending_payload=pend.get("payload"),
                                 seat_map=RD._effective_seat_map(state))
    assert pend["phase"] == phase
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


# --- the hand-submit channel: the unseatable slots fold as not run, as an unseatable audit does ---

def _hand_unseatable_session(tmp_path, name):
    session_dir, gitdir, head_path = TRI._bootstrap(
        tmp_path, name=name, vendors=["claude"], fixerVendor="claude")
    TRI._drive_to_phase(session_dir, gitdir, [TRI._blocking_finding("bounds A", 2)], head_path,
                        RD.P_VERIFIERS)
    state = TRI._state(session_dir)
    state.pop("_advanceUsed", None)  # the same session, now answered by hand
    RD.save_state(session_dir, state)
    return session_dir, state


def test_hand_submitted_verdicts_for_an_unseatable_verifier_do_not_clear_a_finding(tmp_path):
    # axis: the hand-submit fold of an unseatable verifier slot — see bite-proof record
    # wo_b_1797_seat_orders
    session_dir, state = _hand_unseatable_session(tmp_path, "b5-hand-verifiers")
    import verification
    staged = verification.stage_ids(state["_toVerify"])
    assert staged
    artifact = {"verdicts": [{"id": s["id"], "verdict": "REFUTED", "reason": "intentional"}
                             for s in staged]}
    out = RD.cmd_submit(session_dir, RD.P_VERIFIERS, state["pending"]["attempt"],
                        RD.state_hash(state), artifact)
    assert out["ok"], out
    after = TRI._state(session_dir)
    assert not any(d for d in (after["rounds"][str(state["round"])].get("verify") or {}).get("drops", []))
    assert after["rounds"][str(state["round"])]["verify"]["unverified"]


@pytest.mark.parametrize("phase", [RD.P_GAPSWEEP, RD.P_SCOPED])
def test_hand_submit_of_an_unseatable_single_seat_review_phase_is_refused(tmp_path, phase):
    session_dir, state = _hand_unseatable_session(tmp_path, "b5-hand-" + phase)
    state["pending"] = dict(state["pending"], phase=phase)
    RD.save_state(session_dir, state)
    out = RD.cmd_submit(session_dir, phase, state["pending"]["attempt"],
                        RD.state_hash(state), {"findings": []})
    assert out["ok"] is False and out["reason"] == "nonpanel-reviewer-unseatable"
    assert TRI._state(session_dir)["pending"]["phase"] == phase  # the step survives the refusal


def test_hand_submit_guard_reads_the_shared_missing_policy(tmp_path, monkeypatch):
    session_dir, state = _hand_unseatable_session(tmp_path, "b5-policy")
    state["pending"] = dict(state["pending"], phase=RD.P_GAPSWEEP)
    RD.save_state(session_dir, state)
    monkeypatch.setattr(RA, "missing_policy", lambda phase: RA.MISSING_FOLD_FAIL_CLOSED)
    out = RD.cmd_submit(session_dir, RD.P_GAPSWEEP, state["pending"]["attempt"],
                        RD.state_hash(state), {"findings": []})
    assert out.get("reason") != "nonpanel-reviewer-unseatable"
