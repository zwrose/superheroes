"""#1858 (review C5 L5) B1 — a seat map with none of the cell-proof keys proves no non-claude cell.

Each non-panel phase seats a non-claude reviewer only on a vendor whose dispatched cell for that phase
the seat map proves live under a `probed` / `synthesized` source. A map that carries neither
`nonPanelLiveCells` nor `nonPanelLiveCellsSource` (a map that predates them, or no map at all) proves
nothing: the live vendors of the config are no longer proof.

Bite-proof record: plugins/superheroes/lib/tests/bite_proofs/wo_b_1858_nonpanel_cells.md
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
import round_driver as RD  # noqa: E402

NONPANEL = (RD.P_VERIFIERS, RD.P_SEAMS, RD.P_SCOPED)
PHASE_IDS = ("dispatch-verifiers", "dispatch-seams-check", "dispatch-scoped-finder")


def _cells(vendor):
    out = []
    for role in ("verifier", "reviewer-deep"):
        cell = model_registry.matrix_config(role, vendor)
        if cell is not None:
            out.append([vendor, cell[0], cell[1]])
    return out


def _state(seat_map=None, **cfg):
    cfg = dict(cfg, vendors=["claude", "codex"])
    if seat_map is not None:
        cfg["seatMap"] = seat_map
    return {"config": cfg, "rounds": {}, "seatMapReceipts": []}


def _engine(monkeypatch):
    monkeypatch.setattr(RD, "_reviewer_engine_vendor",
                        lambda root: ("claude", RD.VENDOR_SOURCE_CONFIGURED))


def test_the_phase_ids_are_the_driver_phases():
    assert NONPANEL == PHASE_IDS


@pytest.mark.parametrize("phase", NONPANEL)
def test_a_key_less_seat_map_proves_no_non_claude_cell(monkeypatch, phase):
    # axis: a seat map with none of the cell-proof keys proves no non-claude cell — see bite-proof
    # record wo_b_1858_nonpanel_cells (G10)
    _engine(monkeypatch)
    keyless = {"hostFamily": "anthropic", "makerFamilies": ["anthropic"]}
    # claude is barred (anthropic maker); codex is live in the config but its cell is unproven
    assert RD._nonpanel_selection(_state(keyless), None, phase) == (None, None)
    assert RD._nonpanel_unseatable(_state(keyless), None, phase) is True


@pytest.mark.parametrize("phase", NONPANEL)
def test_a_key_less_seat_map_with_its_cells_proven_seats_the_vendor(monkeypatch, phase):
    # positive control for G10: the same map, codex's cells proven `synthesized`
    _engine(monkeypatch)
    proven = {"hostFamily": "anthropic", "makerFamilies": ["anthropic"],
              "nonPanelLiveCells": _cells("codex"), "nonPanelLiveCellsSource": "synthesized"}
    assert RD._nonpanel_selection(_state(proven), None, phase) == ("codex", RD.VENDOR_SOURCE_INDEPENDENT)


@pytest.mark.parametrize("phase", NONPANEL)
def test_no_seat_map_at_all_proves_no_non_claude_cell(monkeypatch, phase):
    _engine(monkeypatch)
    assert RD.effective_seat_map(_state()) == {}
    # the host family is unknown, so claude is ineligible too: nothing is seated
    assert RD._nonpanel_selection(_state(), None, phase) == (None, None)


@pytest.mark.parametrize("role", ["verifier", "reviewer-deep"])
def test_cell_proof_of_a_key_less_or_absent_map_is_false_for_every_non_claude_vendor(role):
    cfg = {"vendors": ["claude", "codex", "cursor"]}
    for seat_map in (None, {}, {"hostFamily": "anthropic"}, {"makerFamilies": ["openai"]}):
        for vendor in ("codex", "cursor"):
            assert RDS.nonpanel_cell_proven(cfg, seat_map, vendor, role) is False
        # the host seat is never probed: claude stays proven (its host family decides eligibility)
        assert RDS.nonpanel_cell_proven(cfg, seat_map, "claude", role) is True
    # the candidate pool is unchanged: the live vendors, with nothing added by the map
    assert RDS.nonpanel_candidates(cfg, {}, role) == ["claude", "codex", "cursor"]
