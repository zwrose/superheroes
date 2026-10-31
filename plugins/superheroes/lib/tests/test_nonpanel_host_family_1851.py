"""#1851 (review C5 L4) — a native host seat takes the seat map's host family.

The non-panel selector and its authentication side judge a native host seat (a registered vendor that
is not a runner-channel vendor, i.e. `claude`) by the seat map's `hostFamily`, not by the registry
family: an unknown host (no seat map, a null or malformed `hostFamily`) leaves it ineligible, and a
host in a maker family bars it.

Bite-proof record: plugins/superheroes/lib/tests/bite_proofs/wo_r_1851_host_family.md
"""
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import model_registry  # noqa: E402
import receipt_disclosures as RDS  # noqa: E402
import round_adapters as RA  # noqa: E402
import round_driver as RD  # noqa: E402

NONPANEL = (RD.P_VERIFIERS, RD.P_SEAMS, RD.P_SCOPED)


def _proof(*vendors):
    """The seat-map keys proving each vendor's dispatched non-panel cells (`verifier`, `reviewer-deep`)
    live: a non-claude reviewer is seated only on proven cells."""
    cells = []
    for role in ("verifier", "reviewer-deep"):
        for vendor in vendors:
            cell = model_registry.matrix_config(role, vendor)
            if cell is not None:
                cells.append([vendor, cell[0], cell[1]])
    return {"nonPanelLiveCells": cells, "nonPanelLiveCellsSource": "synthesized"}


def _map(host="anthropic", **extra):
    out = {"hostFamily": host}
    out.update(extra)
    return out


def _state(seat_map=None, **cfg):
    cfg = dict(cfg)
    if seat_map is not None:
        cfg["seatMap"] = seat_map
    return {"config": cfg, "rounds": {}, "seatMapReceipts": []}


def _engine(monkeypatch, vendor, source=None):
    monkeypatch.setattr(RD, "_reviewer_engine_vendor",
                        lambda root: (vendor, source or RD.VENDOR_SOURCE_CONFIGURED))


def _pick(state, phase=RD.P_VERIFIERS):
    return RD._nonpanel_selection(state, None, phase)


# --- edge 1: no seat map at all -----------------------------------------------------------------

def test_no_seat_map_is_an_unknown_host_and_leaves_native_claude_ineligible(monkeypatch):
    # axis: an unknown host (no seat map) leaves a native claude seat ineligible — see bite-proof
    # record wo_r_1851_host_family (R2)
    _engine(monkeypatch, "claude")
    state = _state(vendors=["claude", "codex"])
    assert RD.effective_seat_map(state) == {}
    assert RDS.host_family(RD.effective_seat_map(state)) is None
    # codex is a runner-channel vendor, unaffected by the host: with its cells proven (a map that
    # names no host family) it is seated in claude's place
    proven = _state(_proof("codex"), vendors=["claude", "codex"])
    assert RDS.host_family(RD.effective_seat_map(proven)) is None
    assert _pick(proven) == ("codex", RD.VENDOR_SOURCE_INDEPENDENT)
    # nothing else to fall to: the only live vendor is the native one on an unknown host
    assert _pick(_state(vendors=["claude"])) == (None, None)
    assert RD._nonpanel_unseatable(_state(vendors=["claude"]), None, RD.P_VERIFIERS)


# --- edge 2: hostFamily null --------------------------------------------------------------------

@pytest.mark.parametrize("host", [None, "", 7, ["anthropic"]])
def test_a_null_or_malformed_host_family_makes_the_native_candidate_ineligible(monkeypatch, host):
    # axis: hostFamily null / not a non-empty string -> native candidate ineligible — see bite-proof
    # record wo_r_1851_host_family (R2)
    _engine(monkeypatch, "claude")
    state = _state(_map(host=host, **_proof("codex")), vendors=["claude", "codex"])
    assert _pick(state) == ("codex", RD.VENDOR_SOURCE_INDEPENDENT)
    assert _pick(_state(_map(host=host), vendors=["claude"])) == (None, None)
    absent = _map()
    del absent["hostFamily"]
    assert _pick(_state(absent, vendors=["claude"])) == (None, None)


# --- edge 3: host family is a maker family ------------------------------------------------------

def test_a_host_in_a_maker_family_bars_native_claude_whatever_its_registry_family(monkeypatch):
    # axis: a native seat takes the HOST family, not family_for("reviewer", "claude") — see bite-proof
    # record wo_r_1851_host_family (R1)
    assert model_registry.family_for("reviewer", "claude") == "anthropic"
    _engine(monkeypatch, "claude")
    openai_host = _state(_map(host="openai", makerFamilies=["openai"]), vendors=["claude", "codex"])
    # claude is barred (host openai == maker openai); codex is openai too -> nobody qualifies
    assert _pick(openai_host) == (None, None)
    # the same maker with an anthropic host: claude is independent and the engine stands
    anthropic_host = _state(_map(host="anthropic", makerFamilies=["openai"]),
                            vendors=["claude", "codex"])
    assert _pick(anthropic_host) == ("claude", RD.VENDOR_SOURCE_CONFIGURED)


def test_the_selection_judges_the_native_seat_by_the_seat_map_host_family(monkeypatch):
    # axis: the selection passes the host family to independent_reviewer — see bite-proof record
    # wo_r_1851_host_family (R4)
    _engine(monkeypatch, "claude")
    state = _state(_map(host="openai", makerFamilies=["openai"]), vendors=["claude"])
    assert _pick(state) == (None, None)
    assert RD._nonpanel_unseatable(state, None, RD.P_VERIFIERS) is True
    row = RD._seat_transport_row(state, RD.P_VERIFIERS, "seat", 0, state["config"], {}, "/repo")
    assert row["vendor"] is None


# --- edge 4: a known, eligible host -------------------------------------------------------------

def test_a_native_candidate_reports_the_host_family_not_the_registry_family():
    cfg = {"vendors": ["claude"]}
    assert RDS.independent_reviewer(cfg, "claude", host_family="openai") == ("claude", "openai")
    assert RDS.independent_reviewer(cfg, "claude", host_family="anthropic") == ("claude", "anthropic")
    # a runner-channel vendor keeps its registry family whatever the host is
    both = {"vendors": ["claude", "codex"]}
    assert RDS.independent_reviewer(both, "codex", host_family="anthropic") == ("codex", "openai")


def test_independent_reviewer_without_the_keyword_keeps_the_registry_family():
    assert RDS.independent_reviewer({"vendors": ["claude"]}, "claude") == ("claude", "anthropic")
    assert RDS.independent_reviewer({"vendors": ["claude", "codex"]}, "claude",
                                    frozenset({"anthropic"})) == ("codex", "openai")


# --- edge 5: authentication side ----------------------------------------------------------------

def test_maker_barred_judges_a_native_seat_with_the_selection_s_host_family():
    # axis: round_adapters._maker_barred passes the host family the selection used — see bite-proof
    # record wo_r_1851_host_family (R3)
    cfg = {"vendors": ["claude", "codex"]}
    bar = RA._maker_barred(_state(_map(host="openai", makerFamilies=["openai"]), **cfg), cfg)
    assert bar("claude") is True
    bar = RA._maker_barred(_state(_map(host="anthropic", makerFamilies=["openai"]), **cfg), cfg)
    assert bar("claude") is False
    # a runner-channel vendor keeps its registry family whatever the host is
    assert bar("codex") is True
    # an unknown host (no seat map) bars the native seat on the authentication side too
    assert RA._maker_barred(_state(**cfg), cfg)("claude") is True


def test_reviewer_ineligible_without_the_keyword_keeps_the_registry_family():
    ineligible = RDS.reviewer_ineligible(frozenset({"openai"}), None)
    assert ineligible("claude") is False and ineligible("codex") is True
    assert RDS.reviewer_ineligible(frozenset({"anthropic"}), None)("claude") is True
    # the keyword never rescues an unregistered vendor: its family cannot be resolved
    assert RDS.reviewer_ineligible(frozenset(), None, host_family="anthropic")("nope") is True


# --- the removed shortcut ------------------------------------------------------------------------

@pytest.mark.parametrize("phase", NONPANEL)
def test_with_no_makers_and_no_fixer_a_native_engine_on_an_unknown_host_is_not_seated(monkeypatch, phase):
    # axis: the removed `not makers and not fixer` shortcut — see bite-proof record
    # wo_r_1851_host_family (R5)
    _engine(monkeypatch, "claude")
    assert phase in NONPANEL
    # unknown host (no seat map): the native engine is ineligible although nothing is barred
    assert _pick(_state(vendors=["claude"]), phase) == (None, None)
    assert _pick(_state(_map(host=None), vendors=["claude"]), phase) == (None, None)
    # a known eligible host: the engine is seated with its own vendorSource
    state = _state(_map(host="anthropic"), vendors=["claude"])
    assert _pick(state, phase) == ("claude", RD.VENDOR_SOURCE_CONFIGURED)
    row = RD._seat_transport_row(state, phase, "seat", 0, state["config"], {}, "/repo")
    assert row["vendor"] == "claude" and row["vendorSource"] == RD.VENDOR_SOURCE_CONFIGURED
    # a defaulted preference read is carried through unchanged
    _engine(monkeypatch, "claude", RD.VENDOR_SOURCE_DEFAULTED)
    assert _pick(state, phase) == ("claude", RD.VENDOR_SOURCE_DEFAULTED)


def test_with_no_makers_and_no_fixer_a_runner_engine_is_unaffected_by_the_host(monkeypatch):
    _engine(monkeypatch, "codex")
    assert _pick(_state(_proof("codex"), vendors=["claude", "codex"])) == (
        "codex", RD.VENDOR_SOURCE_CONFIGURED)
    assert _pick(_state(_map(host=None, **_proof("codex")), vendors=["claude", "codex"])) == (
        "codex", RD.VENDOR_SOURCE_CONFIGURED)
