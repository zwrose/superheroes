"""#1851 (review C5 L4) — the non-panel selector reads per-phase cell proof and the host family.

A non-panel phase seats its reviewer only on a vendor whose dispatched cell for THAT phase (the
`verifier` cell for verifiers, the `reviewer-deep` cell for seams check and scoped) the seat map
proves live; a native host seat takes the seat map's `hostFamily`.

Bite-proof record: plugins/superheroes/lib/tests/bite_proofs/wo_1a_1851_nonpanel_cells.md
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
FINDER_PHASES = (RD.P_SEAMS, RD.P_SCOPED)


def _cell(role, vendor):
    model, effort = model_registry.matrix_config(role, vendor)
    return [vendor, model, effort]


VERIFIER_CELL = {v: _cell("verifier", v) for v in ("codex", "cursor")}
FINDER_CELL = {v: _cell("reviewer-deep", v) for v in ("codex", "cursor")}


def _map(host="anthropic", cells=(), source="probed", **extra):
    out = {"hostFamily": host, "nonPanelLiveCells": list(cells),
           "nonPanelLiveCellsSource": source}
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


def _pick(state, phase):
    return RD._nonpanel_selection(state, None, phase)


# --- edge 1: no seat map at all -----------------------------------------------------------------

@pytest.mark.parametrize("phase", NONPANEL)
def test_no_seat_map_proves_no_cell_and_leaves_native_claude_ineligible(monkeypatch, phase):
    # axis: no seat map proves no non-claude cell, and an unknown host leaves a native claude seat
    # ineligible — see bite-proof record wo_b_1858_nonpanel_cells (G10)
    _engine(monkeypatch, "claude")
    state = _state(vendors=["claude", "codex"])
    assert RD.effective_seat_map(state) == {}
    # codex is live in the config but nothing proves its cell; claude has no known family
    assert _pick(state, phase) == (None, None)
    # nothing else to fall to: the only live vendor is the native one on an unknown host
    assert _pick(_state(vendors=["claude"]), phase) == (None, None)
    assert RD._nonpanel_unseatable(_state(vendors=["claude"]), None, phase)


# --- edge 2: hostFamily null --------------------------------------------------------------------

@pytest.mark.parametrize("phase", NONPANEL)
@pytest.mark.parametrize("host", [None, "", 7, ["anthropic"]])
def test_a_null_or_malformed_host_family_makes_the_native_candidate_ineligible(monkeypatch, phase, host):
    # axis: hostFamily null / not a non-empty string -> native candidate ineligible — see bite-proof
    # record wo_1a_1851_nonpanel_cells (G6)
    _engine(monkeypatch, "claude")
    cells = [VERIFIER_CELL["codex"], FINDER_CELL["codex"]]
    state = _state(_map(host=host, cells=cells), vendors=["claude", "codex"])
    assert _pick(state, phase) == ("codex", RD.VENDOR_SOURCE_INDEPENDENT)
    assert _pick(_state(_map(host=host), vendors=["claude"]), phase) == (None, None)
    absent = _map()
    del absent["hostFamily"]
    assert _pick(_state(absent, vendors=["claude"]), phase) == (None, None)


# --- edge 3: host family is a maker family ------------------------------------------------------

@pytest.mark.parametrize("phase", NONPANEL)
def test_a_host_in_a_maker_family_bars_native_claude_whatever_its_registry_family(monkeypatch, phase):
    # axis: a native seat takes the HOST family, not family_for("reviewer", "claude") — see bite-proof
    # record wo_1a_1851_nonpanel_cells (G5)
    assert model_registry.family_for("reviewer", "claude") == "anthropic"
    _engine(monkeypatch, "claude")
    cells = [VERIFIER_CELL["codex"], FINDER_CELL["codex"]]
    openai_host = _state(_map(host="openai", cells=cells, makerFamilies=["openai"]),
                         vendors=["claude", "codex"])
    # claude is barred (host openai == maker openai); codex is openai too -> nobody qualifies
    assert _pick(openai_host, phase) == (None, None)
    # the same maker with an anthropic host: claude is independent and the engine stands
    anthropic_host = _state(_map(host="anthropic", cells=cells, makerFamilies=["openai"]),
                            vendors=["claude", "codex"])
    assert _pick(anthropic_host, phase) == ("claude", RD.VENDOR_SOURCE_CONFIGURED)


def test_a_native_candidate_reports_the_host_family_not_the_registry_family():
    sm = _map(host="openai")
    assert RDS.nonpanel_reviewer({"vendors": ["claude"]}, sm, "verifier", "claude") == ("claude", "openai")
    assert RDS.nonpanel_reviewer({"vendors": ["claude", "codex"]}, _map(cells=[VERIFIER_CELL["codex"]]),
                                 "verifier", "codex") == ("codex", "openai")


def test_maker_barred_judges_a_native_seat_with_the_selection_s_host_family():
    # axis: round_adapters._maker_barred passes the host family the selection used — see bite-proof
    # record wo_1a_1851_nonpanel_cells (G7)
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


# --- edge 4: an unprobed source proves no non-claude vendor -------------------------------------

@pytest.mark.parametrize("phase", NONPANEL)
def test_an_unprobed_source_proves_no_non_claude_cell(monkeypatch, phase):
    # axis: the cell-membership check (a listed cell counts only under a probed / synthesized
    # source) — see bite-proof record wo_1a_1851_nonpanel_cells (G2)
    _engine(monkeypatch, "claude")
    cells = [VERIFIER_CELL["codex"], FINDER_CELL["codex"]]
    state = _state(_map(cells=cells, source="unprobed"), vendors=["claude", "codex"], fixerVendor="claude")
    assert _pick(state, phase) == (None, None)
    # claude is a host seat and never probed: with no fixer it is still seated on an unprobed map
    assert _pick(_state(_map(cells=cells, source="unprobed"), vendors=["claude", "codex"]),
                 phase) == ("claude", RD.VENDOR_SOURCE_CONFIGURED)


# --- edge 5: source present, cells missing / not a list / malformed -----------------------------

@pytest.mark.parametrize("phase", NONPANEL)
@pytest.mark.parametrize("source", ["probed", "synthesized"])
def test_missing_or_non_list_cells_prove_nothing(monkeypatch, phase, source):
    # axis: unknown / partial evidence is NOT proven (no fallback to the legacy rule) — see bite-proof
    # record wo_1a_1851_nonpanel_cells (G3)
    _engine(monkeypatch, "claude")
    for bad in ("absent", None, "codex", {"codex": 1}, 7):
        sm = {"hostFamily": "anthropic", "nonPanelLiveCellsSource": source}
        if bad != "absent":
            sm["nonPanelLiveCells"] = bad
        state = _state(sm, vendors=["claude", "codex"], fixerVendor="claude")
        assert _pick(state, phase) == (None, None), bad


@pytest.mark.parametrize("phase", NONPANEL)
@pytest.mark.parametrize("source", [None, "bogus", 7, ["probed"], ""])
def test_an_unknown_or_non_string_source_proves_nothing(monkeypatch, phase, source):
    _engine(monkeypatch, "claude")
    sm = _map(cells=[VERIFIER_CELL["codex"], FINDER_CELL["codex"]])
    sm["nonPanelLiveCellsSource"] = source
    state = _state(sm, vendors=["claude", "codex"], fixerVendor="claude")
    assert _pick(state, phase) == (None, None)


@pytest.mark.parametrize("phase", NONPANEL)
def test_malformed_cell_entries_are_skipped_and_the_valid_ones_still_count(monkeypatch, phase):
    _engine(monkeypatch, "claude")
    junk = [None, "codex", 5, ["codex"], ["codex", "gpt-6.1-sol"], [1, 2, 3], ["", "m", None],
            ["codex", "", None], {"vendor": "codex"}]
    state = _state(_map(cells=junk), vendors=["claude", "codex"], fixerVendor="claude")
    assert _pick(state, phase) == (None, None)
    both = junk + [VERIFIER_CELL["codex"], FINDER_CELL["codex"]]
    state = _state(_map(cells=both), vendors=["claude", "codex"], fixerVendor="claude")
    assert _pick(state, phase) == ("codex", RD.VENDOR_SOURCE_INDEPENDENT)


# --- edge 6: one or two of the three keys -------------------------------------------------------

@pytest.mark.parametrize("phase", NONPANEL)
@pytest.mark.parametrize("keep", [("hostFamily",), ("nonPanelLiveCells",), ("nonPanelLiveCellsSource",),
                                  ("hostFamily", "nonPanelLiveCells"),
                                  ("hostFamily", "nonPanelLiveCellsSource"),
                                  ("nonPanelLiveCells", "nonPanelLiveCellsSource")])
def test_a_partial_seat_map_is_not_legacy_and_proves_only_what_it_carries(monkeypatch, phase, keep):
    # axis: partial evidence is unproved, never the legacy live-vendor rule — see bite-proof record
    # wo_1a_1851_nonpanel_cells (G3)
    _engine(monkeypatch, "codex")
    full = _map(cells=[VERIFIER_CELL["codex"], FINDER_CELL["codex"]])
    sm = {k: v for k, v in full.items() if k in keep}
    state = _state(sm, vendors=["claude", "codex"], fixerVendor="claude")
    got = _pick(state, phase)
    if set(keep) == {"nonPanelLiveCells", "nonPanelLiveCellsSource"}:
        # source + cells present: codex is proven (the host family is irrelevant to a runner seat)
        assert got == ("codex", RD.VENDOR_SOURCE_CONFIGURED)
    else:
        # codex is live in the config, yet a partial map does not prove its cell
        assert got == (None, None)


# --- edge 7: proven for one phase, not the other ------------------------------------------------

def test_a_vendor_proven_for_verifiers_only_is_not_seated_for_seams_check_or_scoped(monkeypatch):
    # axis: the phase -> cell role mapping (verifier vs reviewer-deep) — see bite-proof record
    # wo_1a_1851_nonpanel_cells (G1)
    _engine(monkeypatch, "codex")
    state = _state(_map(cells=[VERIFIER_CELL["codex"]]), vendors=["claude", "codex"],
                   fixerVendor="claude")
    assert _pick(state, RD.P_VERIFIERS) == ("codex", RD.VENDOR_SOURCE_CONFIGURED)
    for phase in FINDER_PHASES:
        assert _pick(state, phase) == (None, None)
        assert RD._nonpanel_unseatable(state, None, phase)
    row = RD._seat_transport_row(state, RD.P_SEAMS, "seat", 0, state["config"], {}, "/repo")
    assert row["vendor"] is None


def test_a_vendor_proven_for_the_finder_phases_only_is_not_seated_for_verifiers(monkeypatch):
    # axis: the cell-membership check (a listed cell counts only for its own phase's cell) — see
    # bite-proof record wo_1a_1851_nonpanel_cells (G2)
    _engine(monkeypatch, "codex")
    state = _state(_map(cells=[FINDER_CELL["codex"]]), vendors=["claude", "codex"],
                   fixerVendor="claude")
    assert _pick(state, RD.P_VERIFIERS) == (None, None)
    for phase in FINDER_PHASES:
        assert _pick(state, phase) == ("codex", RD.VENDOR_SOURCE_CONFIGURED)
    row = RD._seat_transport_row(state, RD.P_VERIFIERS, "verifier:c1", 0, state["config"], {}, "/repo")
    assert row["vendor"] is None
    row = RD._seat_transport_row(state, RD.P_SCOPED, "scoped", 0, state["config"], {}, "/repo")
    assert row["vendor"] == "codex"


def test_a_listed_cell_at_the_wrong_effort_does_not_prove_the_phase_cell(monkeypatch):
    _engine(monkeypatch, "codex")
    wrong = ["codex", VERIFIER_CELL["codex"][1], "low"]
    state = _state(_map(cells=[wrong]), vendors=["claude", "codex"], fixerVendor="claude")
    assert all(_pick(state, phase) == (None, None) for phase in NONPANEL)
    # a tuple-shaped entry normalizes like a list one
    state = _state(_map(cells=[tuple(VERIFIER_CELL["codex"])]), vendors=["claude", "codex"],
                   fixerVendor="claude")
    assert _pick(state, RD.P_VERIFIERS)[0] == "codex"


# --- edge 8: proven by cells but absent from config["vendors"] ----------------------------------

@pytest.mark.parametrize("phase", NONPANEL)
def test_a_cell_proven_vendor_outside_the_configured_vendors_is_still_a_candidate(monkeypatch, phase):
    # axis: the pool extension (I2) — see bite-proof record wo_1a_1851_nonpanel_cells (G4)
    _engine(monkeypatch, "claude")
    cells = [VERIFIER_CELL["cursor"], FINDER_CELL["cursor"]]
    state = _state(_map(cells=cells), vendors=["claude"], fixerVendor="claude")
    assert _pick(state, phase) == ("cursor", RD.VENDOR_SOURCE_INDEPENDENT)
    row = RD._seat_transport_row(state, phase, "seat", 0, state["config"], {}, "/repo")
    assert row["vendor"] == "cursor" and row["vendorSource"] == RD.VENDOR_SOURCE_INDEPENDENT


def test_the_pool_is_live_vendors_then_proven_registry_vendors_in_registry_order():
    sm = _map(cells=[VERIFIER_CELL["cursor"], VERIFIER_CELL["codex"]])
    assert RDS.nonpanel_candidates({"vendors": ["cursor"]}, sm, "verifier") == ["cursor", "codex"]
    assert RDS.nonpanel_candidates({"vendors": ["claude"]}, sm, "verifier") == ["claude", "codex", "cursor"]
    # codex's finder cell (xhigh) is not listed, so the finder pool does not gain it
    assert RDS.nonpanel_candidates({"vendors": ["claude"]}, sm, "reviewer-deep") == ["claude", "cursor"]
    # a legacy map, or one with no usable evidence, adds nothing
    assert RDS.nonpanel_candidates({"vendors": ["claude"]}, {}, "verifier") == ["claude"]
    assert RDS.nonpanel_candidates({"vendors": ["claude"]}, _map(cells=[VERIFIER_CELL["codex"]],
                                                                  source="unprobed"),
                                   "verifier") == ["claude"]


def test_the_preferred_vendor_goes_first_when_it_is_a_candidate():
    sm = _map(cells=[VERIFIER_CELL["codex"], VERIFIER_CELL["cursor"]])
    cfg = {"vendors": ["claude", "codex"]}
    assert RDS.nonpanel_reviewer(cfg, sm, "verifier", "cursor")[0] == "cursor"
    assert RDS.nonpanel_reviewer(cfg, sm, "verifier", "codex")[0] == "codex"
    assert RDS.nonpanel_reviewer(cfg, sm, "verifier", None)[0] == "claude"
    assert RDS.nonpanel_reviewer(cfg, sm, "verifier", "not-a-vendor")[0] == "claude"


# --- edge 9: no makers, no fixer, engine unproven (the removed shortcut) ------------------------

@pytest.mark.parametrize("phase", NONPANEL)
def test_with_nothing_barred_an_unproven_engine_cell_is_still_not_seated(monkeypatch, phase):
    # axis: the removed `not makers and not fixer` shortcut — see bite-proof record
    # wo_1a_1851_nonpanel_cells (G8)
    _engine(monkeypatch, "codex")
    state = _state(_map(cells=[]), vendors=["claude", "codex"])
    # codex is the engine but its cell is unproven: the next qualifying candidate (the host seat)
    assert _pick(state, phase) == ("claude", RD.VENDOR_SOURCE_INDEPENDENT)
    # a defaulted preference read stays disclosed when the engine is replaced
    _engine(monkeypatch, "codex", RD.VENDOR_SOURCE_DEFAULTED)
    assert _pick(state, phase) == ("claude", RD.VENDOR_SOURCE_DEFAULTED)
    # and an unknown host leaves nothing to fall to
    _engine(monkeypatch, "codex")
    assert _pick(_state(_map(host=None, cells=[]), vendors=["claude", "codex"]), phase) == (None, None)


@pytest.mark.parametrize("phase", NONPANEL)
def test_with_nothing_barred_a_qualifying_engine_keeps_its_vendor_and_source(monkeypatch, phase):
    cells = [VERIFIER_CELL["codex"], FINDER_CELL["codex"]]
    state = _state(_map(cells=cells), vendors=["claude", "codex"])
    _engine(monkeypatch, "codex")
    assert _pick(state, phase) == ("codex", RD.VENDOR_SOURCE_CONFIGURED)
    _engine(monkeypatch, "claude", RD.VENDOR_SOURCE_DEFAULTED)
    assert _pick(state, phase) == ("claude", RD.VENDOR_SOURCE_DEFAULTED)


# --- edge 10: every candidate fails -------------------------------------------------------------

@pytest.mark.parametrize("phase", NONPANEL)
def test_when_every_candidate_fails_the_seat_is_unseatable(monkeypatch, phase):
    _engine(monkeypatch, "codex")
    state = _state(_map(host="openai", cells=[], makerFamilies=["openai"]), vendors=["claude", "codex"])
    assert _pick(state, phase) == (None, None)
    assert RD._nonpanel_unseatable(state, None, phase) is True
    row = RD._seat_transport_row(state, phase, "seat", 0, state["config"], {}, "/repo")
    assert row["vendor"] is None


# --- I5: the phase is required everywhere -------------------------------------------------------

def test_the_non_panel_helpers_require_the_phase():
    state = _state(_map(), vendors=["claude"])
    with pytest.raises(TypeError):
        RD._nonpanel_selection(state, None)
    with pytest.raises(TypeError):
        RD._nonpanel_unseatable(state, None)
    with pytest.raises(TypeError):
        RD._nonpanel_reviewer_vendor(state, state["config"], "/repo")


def test_every_non_panel_phase_maps_to_a_cell_role():
    assert RD._NONPANEL_PHASE_ROLE == {RD.P_VERIFIERS: "verifier", RD.P_SEAMS: "reviewer-deep",
                                       RD.P_SCOPED: "reviewer-deep", RD.P_SYNTHESIS: "synthesis",
                                       RD.P_SECOND_TEST: "reviewer-deep"}
    assert set(RD._NONPANEL_PHASE_ROLE) == set(RD._NONPANEL_REVIEWER_PHASES) | {RD.P_SYNTHESIS}


# --- I1: the claude host rule, read directly -----------------------------------------------------

def test_cell_proof_rules_read_directly():
    cfg = {"vendors": ["claude", "codex"]}
    # claude is a host seat: proven on every shape, even an unprobed one
    for sm in ({}, _map(source="unprobed"), {"nonPanelLiveCells": "x"}):
        assert RDS.nonpanel_cell_proven(cfg, sm, "claude", "verifier") is True
    # a key-less or absent map proves no non-claude cell
    assert RDS.nonpanel_cell_proven(cfg, {}, "codex", "verifier") is False
    assert RDS.nonpanel_cell_proven(cfg, {}, "cursor", "verifier") is False
    assert RDS.nonpanel_cell_proven(cfg, None, "codex", "reviewer-deep") is False
    # evidence present: only a listed cell
    sm = _map(cells=[VERIFIER_CELL["codex"]], source="synthesized")
    assert RDS.nonpanel_cell_proven(cfg, sm, "codex", "verifier") is True
    assert RDS.nonpanel_cell_proven(cfg, sm, "codex", "reviewer-deep") is False
    assert RDS.nonpanel_cell_proven(cfg, sm, "cursor", "verifier") is False
    # unknown role / vendor / non-string vendor prove nothing
    assert RDS.nonpanel_cell_proven(cfg, sm, "codex", "implementer") is False
    assert RDS.nonpanel_cell_proven(cfg, sm, "nope", "verifier") is False
    assert RDS.nonpanel_cell_proven(cfg, sm, None, "verifier") is False
