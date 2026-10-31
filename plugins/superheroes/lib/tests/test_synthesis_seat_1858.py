"""The synthesis (grouping) seat is a non-panel seat: seated on a vendor outside every maker family
and the fixer's vendor whose synthesis cell is proven live (the native host `claude` stands on a known,
non-maker `hostFamily`); with none, no synthesis order is emitted, the driver records
`synthesisUnseatable`, the round folds no grouping (every verified finding stays separate) and the
receipt discloses it. A grouping from a seat other than the recorded one, or from a barred vendor,
does not count.

Edges: c1 makers include anthropic and openai · c2 positive control · c3 unknown host, no proven codex
cell · c4 fixer is claude, no proven codex cell · c5 durable landing from another / barred vendor ·
c6 hand submit while unseatable · c7 library callback vendor · c8 an ordinary missing result while
seatable · c9 a Claude-built PR's grouping pass seats on codex when the map proves that cell.

The registry lists a codex synthesis cell on the triple of its verifier cell, so a map that proves the
codex verifier cell proves the grouping cell too: an "unseatable" case bars codex as well (the makers
include `openai`, or the map proves no codex cell). The round-level cases keep the verifier seated on
`cursor` (outside the barred families), whose synthesis cell the registry does not list.

Bite-proof record: plugins/superheroes/lib/tests/bite_proofs/wo_c_1858_synthesis_seat.md
"""
import os
import sys
from pathlib import Path

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
_EVAL = os.path.join(os.path.dirname(_LIB), "eval")
for _p in (_HERE, _LIB, _EVAL):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import round_adapters as RA  # noqa: E402
import round_driver as RD  # noqa: E402
import test_nonpanel_independence_1797 as NI  # noqa: E402
import test_round_driver as TRD  # noqa: E402
import test_round_driver_integration as TRI  # noqa: E402
import test_verifier_vendor_provenance_1797 as P17  # noqa: E402
import review_loop_runner as HARNESS  # noqa: E402

UNSEATABLE_LINE = "synthesis-unseatable (round 1)"
# claude and codex are barred by the makers; the verifier seats on cursor, which has no synthesis cell
_VERIFIER_ONLY = {"fixer": "claude", "makers": ["anthropic", "openai"],
                  "proven": ("claude", "codex", "cursor"), "vendors": ["claude", "codex", "cursor"]}
_A_FINDING = [{"title": "bug", "severity": "Important", "file": "f.py", "line": 1,
               "consequence": "a reviewer-found defect stays in the change"}]


def _seat_map(host="anthropic", makers=(), proven=("claude", "codex")):
    """A seat map proving the `proven` vendors' non-panel cells; `makers` fills `makerFamilies`."""
    seat_map = TRD._nonpanel_cell_proof(list(proven))
    if host is not None:
        seat_map["hostFamily"] = host
    if makers:
        seat_map["makerFamilies"] = list(makers)
    return seat_map


def _cfg(fixer="cursor", host="anthropic", makers=(), proven=("claude", "codex"), vendors=None):
    return {"repoRoot": "/nonexistent-review-project", "vendors": list(vendors or ["claude", "codex"]),
            "fixerVendor": fixer, "seatMap": _seat_map(host, makers, proven)}


def _state(**kw):
    return RD.new_state(_cfg(**kw))


def _selection(**kw):
    return RD._nonpanel_selection(_state(**kw), None, RD.P_SYNTHESIS)


def _engine(monkeypatch, vendor):
    # `run_loop` runs on test_round_driver's own load of the module (`TRD.RD`), not this file's import
    for module in (RD, TRD.RD):
        monkeypatch.setattr(module, "_reviewer_engine_vendor",
                            lambda root: (vendor, RD.VENDOR_SOURCE_CONFIGURED))


def _lib_run(monkeypatch, engine, synthesis, verifier_vendor, findings=None, **cfg_kw):
    """run_loop on a round that reports `findings` (one by default); returns (result, loop receipt,
    state)."""
    _engine(monkeypatch, engine)
    reported = _A_FINDING if findings is None else findings

    def reviewer(dim, tier, rnd, ctx):
        return [dict(f) for f in reported] if rnd == 1 and dim == "code-reviewer" else []

    def verifier(clusters, rnd):
        return {"verdicts": [{"id": i, "verdict": "CONFIRMED", "evidence": "ran", "reason": "ran"}
                             for c in (clusters or []) for i in (c.get("ids") or [])],
                "vendor": verifier_vendor}

    seams = TRD._seams(reviewer=reviewer, verifier=verifier, synthesis=synthesis)
    result, state = TRD._run_loop_capturing_state(seams, TRD._cfg_cert(**_cfg(**cfg_kw)))
    return result, RD.build_receipt(state), state


def _cli_run(tmp_path, **cfg_kw):
    """Drive next/submit to a terminal with one finding; returns (phases offered, state, receipt)."""
    session_dir = str(tmp_path)
    seen = []
    base = TRD._responder(round1_findings=_A_FINDING)

    def respond(phase, payload, rnd):
        seen.append(phase)
        art = base(phase, payload, rnd)
        if phase == RD.P_VERIFIERS:
            ok, state = RD.load_state(session_dir)
            art = dict(art, verifierVendor=RD._nonpanel_selection(state, session_dir, phase)[0])
        return art

    cfg = _cfg(**cfg_kw)
    cfg.pop("repoRoot")  # the driven session runs in a real checkout
    TRD._drive_cli(session_dir, TRD._cfg(**cfg), respond)
    ok, state = RD.load_state(session_dir)
    assert ok
    return seen, state, RD.build_receipt(state)


# --- the selection: c1 / c2 / c3 / c4 ---------------------------------------------------------

def test_c2_the_synthesis_seat_is_seated_on_claude_outside_the_makers():
    # axis: the synthesis role is a non-panel role — seated on the proven native cell (positive control)
    assert RD._NONPANEL_PHASE_ROLE[RD.P_SYNTHESIS] == "synthesis"
    assert _selection()[0] == "claude"
    assert RD._nonpanel_unseatable(_state(), None, RD.P_SYNTHESIS) is False


@pytest.mark.parametrize("kw", [
    pytest.param({"makers": ["anthropic", "openai"]}, id="c1-makers-include-anthropic"),
    pytest.param({"host": None, "proven": ("claude",)}, id="c3-unknown-host-family"),
    pytest.param({"fixer": "claude", "proven": ("claude",)}, id="c4-fixer-is-claude"),
])
def test_c1_c3_c4_no_vendor_qualifies_so_the_synthesis_seat_is_unseatable(kw):
    # axis: makers / unknown host / fixer bar every synthesis cell the map proves (claude, and codex when proven)
    assert _selection(**kw) == (None, None)
    assert RD._nonpanel_unseatable(_state(**kw), None, RD.P_SYNTHESIS) is True
    row = RD._seat_transport_row(_state(**kw), RD.P_SYNTHESIS, "synthesis", 0,
                                 _state(**kw)["config"], {}, "/nonexistent-review-project")
    assert row["vendor"] is None


def test_c9_a_claude_built_prs_grouping_pass_seats_on_codex_when_the_map_proves_the_cell():
    # axis: the grouping pass seats on a non-maker vendor whose synthesis cell the map proves (codex, openai)
    state = _state(makers=["anthropic"])
    assert RD._nonpanel_selection(state, None, RD.P_SYNTHESIS)[0] == "codex"
    assert RD._nonpanel_unseatable(state, None, RD.P_SYNTHESIS) is False
    row = RD._seat_transport_row(state, RD.P_SYNTHESIS, "synthesis", 0, state["config"], {},
                                 "/nonexistent-review-project")
    assert row["vendor"] == "codex"
    family = RD.receipt_disclosures.nonpanel_reviewer(
        state["config"], state["config"]["seatMap"], "synthesis", "codex",
        frozenset({"anthropic"}), "cursor")[1]
    assert family == "openai"


def test_c9_library_a_claude_built_prs_grouping_runs_on_codex(monkeypatch):
    # axis: a codex-seated synthesis is called and records no `synthesisUnseatable`
    calls = []
    _result, loop_receipt, state = _lib_run(
        monkeypatch, "codex", lambda findings, rnd: calls.append(rnd), "codex", makers=["anthropic"])
    assert calls == [1]
    assert "synthesisUnseatable" not in state["rounds"]["1"]
    assert not any(UNSEATABLE_LINE in line for line in loop_receipt.get("degraded") or [])


def test_c2_the_transport_row_names_the_synthesis_selection():
    state = _state()
    row = RD._seat_transport_row(state, RD.P_SYNTHESIS, "synthesis", 0, state["config"], {},
                                 "/nonexistent-review-project")
    assert row["vendor"] == "claude" and "vendorSource" in row


# --- c1: the round continues with no grouping (library and CLI) -------------------------------

def test_c1_library_unseatable_synthesis_emits_no_seam_call_and_discloses(monkeypatch):
    # axis: the chokepoint gate — an unseatable synthesis never calls the callback, records the channel
    calls = []
    result, loop_receipt, state = _lib_run(
        monkeypatch, "cursor", lambda findings, rnd: calls.append(rnd), "cursor", **_VERIFIER_ONLY)
    assert calls == []
    assert state["rounds"]["1"]["synthesisUnseatable"] == [
        {"makerFamilies": ["anthropic", "openai"], "fixerVendor": "claude"}]
    assert any(d["kind"] == "synthesis-unseatable" for d in state["decisions"])
    assert state["terminal"] != "cannot-certify", state.get("certification")
    assert any(UNSEATABLE_LINE in line for line in loop_receipt["degraded"]), loop_receipt["degraded"]


def test_c1_library_unseatable_synthesis_drops_nothing(monkeypatch):
    """The unseatable-grouping path (`_nonpanel_unseatable(state, session_dir, P_SYNTHESIS)` into
    `_fold_synthesis(state, config, {"grouping": None})`) keeps both verified findings, separate.

    axis: an unseatable synthesis seat folds no grouping, so every verified finding survives the fold
    — see bite-proof record c7l3_wo3_driver"""
    two = [dict(_A_FINDING[0]), dict(_A_FINDING[0], line=2)]
    calls = []
    result, loop_receipt, state = _lib_run(
        monkeypatch, "cursor", lambda findings, rnd: calls.append(rnd), "cursor", findings=two,
        **_VERIFIER_ONLY)
    assert calls == []
    assert state["rounds"]["1"]["synthesisUnseatable"]
    assert state["rounds"]["1"]["merges"] == []
    ledger = {RD.session_contract.finding_identity_key(e): e
              for e in state[RD.session_contract.DISPOSITION_LEDGER_KEY]}
    assert sorted(ledger) == ["f.py::bug@L1", "f.py::bug@L2"], sorted(ledger)
    # both reached the fixer and were audited: a finding dropped at the fold would be settled instead
    assert [ledger[k]["disposition"] for k in sorted(ledger)] == ["fixed", "fixed"], ledger


def test_c1_cli_unseatable_synthesis_is_never_offered_and_the_round_continues(tmp_path):
    # axis: the empty-grouping fold at the chokepoint — the step never becomes dispatch-synthesis
    seen, state, receipt = _cli_run(tmp_path, **_VERIFIER_ONLY)
    assert RD.P_SYNTHESIS not in seen
    assert RD.P_APPLY_FIXES in seen, seen
    assert state["rounds"]["1"]["synthesisUnseatable"]
    assert state["terminal"] != "cannot-certify", state.get("certification")
    assert any(UNSEATABLE_LINE in line for line in receipt["degraded"]), receipt["degraded"]


def test_c2_cli_a_seatable_synthesis_is_offered_and_discloses_nothing(tmp_path):
    seen, state, receipt = _cli_run(tmp_path)
    assert RD.P_SYNTHESIS in seen
    assert "synthesisUnseatable" not in state["rounds"]["1"]
    assert not any(UNSEATABLE_LINE in line for line in receipt.get("degraded") or [])


# --- c5: the durable landing is authenticated against the emission ----------------------------

def _synthesis_env(source):
    env = P17._finder_envelope(RA.SEAT_SYNTHESIS, source=source)
    env["payload"] = {"grouping": None}
    return env


def _assemble(state, source, recorded="claude"):
    return RA.assemble(RD.P_SYNTHESIS, [_synthesis_env(source)], state, state["config"],
                       orders_manifest=P17._finder_manifest(RA.SEAT_SYNTHESIS, vendor=recorded))


def test_c5_durable_synthesis_executed_on_the_recorded_vendor_counts():
    art, why = _assemble(_state(), "claude")
    assert why is None and art["grouping"] is None


def test_c5_durable_synthesis_executed_on_another_vendor_is_refused():
    # axis: the durable landing authenticates the executed vendor against the recorded one (S4)
    art, why = _assemble(_state(), "codex")
    assert art is None and why.startswith("missing-seat-refuse-fold:%s" % RA.SEAT_SYNTHESIS), (art, why)
    assert "executed=codex" in why and "recorded=claude" in why


def test_c5_durable_synthesis_from_a_barred_vendor_is_refused():
    art, why = _assemble(_state(makers=["anthropic"]), "claude")
    assert art is None and why.endswith(":vendor-ineligible"), (art, why)


# --- c6: a hand synthesis artifact for an unseatable seat is refused --------------------------

def test_c6_hand_submit_of_an_unseatable_synthesis_is_refused(tmp_path):
    # axis: the hand-submit refusal covers the synthesis phase (S5)
    session_dir, state = NI._hand_unseatable_session(tmp_path, "c6-hand")
    state["pending"] = dict(state["pending"], phase=RD.P_SYNTHESIS)
    RD.save_state(session_dir, state)
    out = RD.cmd_submit(session_dir, RD.P_SYNTHESIS, state["pending"]["attempt"],
                        RD.state_hash(state), {"grouping": None})
    assert out["ok"] is False and out["reason"] == "nonpanel-reviewer-unseatable", out
    assert TRI._state(session_dir)["pending"]["phase"] == RD.P_SYNTHESIS


def test_c6_hand_submit_of_a_seatable_synthesis_without_a_vendor_claim_is_accepted(tmp_path):
    session_dir, gitdir, head_path = TRI._bootstrap(
        tmp_path, name="c6-seatable", fixerVendor="cursor", seatMap=dict(TRI.SEAT_MAP, hostFamily="anthropic"))
    TRI._drive_to_phase(session_dir, gitdir, [TRI._blocking_finding("bounds A", 2)], head_path,
                        RD.P_SYNTHESIS)
    state = TRI._state(session_dir)
    state.pop("_advanceUsed", None)
    RD.save_state(session_dir, state)
    out = RD.cmd_submit(session_dir, RD.P_SYNTHESIS, state["pending"]["attempt"],
                        RD.state_hash(state), {"grouping": None})
    assert out["ok"] is True, out


# --- c7: the library callback's reported vendor -----------------------------------------------

def test_c7_library_synthesis_reporting_another_vendor_parks(monkeypatch):
    # axis: the library vendor check judges a reported synthesis vendor against the captured selection (S6)
    _result, _receipt, state = _lib_run(
        monkeypatch, "claude", lambda findings, rnd: {"grouping": None, "vendor": "codex"}, "claude")
    assert state["terminal"] == "cannot-certify"
    assert state["certification"]["reason"] == \
        "nonpanel-synthesis-unauthenticated:expected=claude:reported=codex", state["certification"]


@pytest.mark.parametrize("reply", [None, {"grouping": None, "vendor": "claude"}], ids=["bare", "selection"])
def test_c7_library_synthesis_bare_or_matching_report_is_accepted(monkeypatch, reply):
    calls = []

    def synthesis(findings, rnd):
        calls.append(rnd)
        return reply

    _result, _receipt, state = _lib_run(monkeypatch, "claude", synthesis, "claude")
    assert calls, "the seatable synthesis must have been called"
    assert state["terminal"] != "cannot-certify", state.get("certification")


# --- c8: an ordinary missing result while seatable keeps the refuse-fold ----------------------

def test_c8_a_missing_synthesis_result_while_seatable_is_still_refused():
    assert RA.missing_policy(RD.P_SYNTHESIS) == RA.MISSING_REFUSE_FOLD
    state = _state()
    art, why = RA.assemble(RD.P_SYNTHESIS, [], state, state["config"],
                           orders_manifest=P17._finder_manifest(RA.SEAT_SYNTHESIS, vendor="claude"))
    assert art is None and why == "missing-seat-refuse-fold:%s" % RA.SEAT_SYNTHESIS, (art, why)


# --- B5: the eval harness counts synthesis only when the callback ran --------------------------

def test_b5_the_harness_counts_a_synthesis_leaf_only_for_a_round_that_ran_it(monkeypatch):
    # axis: the expected synthesis leaf follows the callback having run, not the round having been seen
    fixture = Path(_EVAL) / "fixtures" / "review_loop" / "confirmation_important_certifies.json"
    clean = HARNESS._eval_clean_seat_map

    def without_codex_cells(fixer_vendor=HARNESS._EVAL_FIXER_VENDOR):
        seat_map = dict(clean(fixer_vendor))
        seat_map["nonPanelLiveCells"] = [c for c in seat_map["nonPanelLiveCells"] if c[0] != "codex"]
        return seat_map

    # the harness seat map carries no host family and (here) no proven codex cell, so its synthesis
    # seat is unseatable: no leaf
    monkeypatch.setattr(HARNESS, "_eval_clean_seat_map", without_codex_cells)
    leaves = HARNESS.run_fixture(fixture)["telemetry"]["tokenUsage"]["expectedLeaves"]
    assert not [leaf for leaf in leaves if leaf.startswith("synthesis:")], leaves
    monkeypatch.setattr(HARNESS, "_eval_clean_seat_map",
                        lambda fixer_vendor=HARNESS._EVAL_FIXER_VENDOR: dict(clean(fixer_vendor),
                                                                             hostFamily="google"))
    # a known non-maker host family seats it on `claude`: the callback runs and its leaf is counted
    ran = HARNESS.run_fixture(fixture)["telemetry"]["tokenUsage"]["expectedLeaves"]
    assert "synthesis:r1" in ran, ran
