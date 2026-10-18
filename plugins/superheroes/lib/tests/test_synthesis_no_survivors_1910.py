"""A review with zero verified survivors folds synthesis without dispatching it (#1910).

After the verifier fold, a round whose verified survivors (`state["_verified"]`) are empty never
emits a synthesis order: the driver folds an empty grouping itself, records `synthesis-no-survivors`,
and the round continues to its next step exactly as a seat returning `{"grouping": []}` would have.
A round with survivors is unchanged: synthesis is dispatched; a hand-submitted empty grouping means
"nothing to merge" (every survivor stays separate, none is dropped), and a durable empty grouping with
no runner execution evidence is refused.

Edges: E1 every finding REFUTED (T2) · E2 the panel reported nothing, so the verifier roster was
empty (T1) · E3 survivors exist, synthesis is still offered (T3) · E4 a hand-submitted empty grouping
over survivors is accepted as "nothing to merge" and drops nothing (T3) · E5 a durable empty grouping with no runner execution evidence is
refused (T4) · E6 the skip sits before the unseatable branch (T2b runs on an unseatable cell, so it
shows the order is withheld by the skip and not by the unseatable gate).

Bite-proof record: plugins/superheroes/lib/tests/bite_proofs/wo_1_1910_synthesis_no_survivors.md
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import round_adapters as RA  # noqa: E402
import test_round_driver as TRD  # noqa: E402
import test_round_driver_advance as ADV  # noqa: E402
import test_synthesis_seat_1858 as S1858  # noqa: E402
import test_verifier_vendor_provenance_1797 as P17  # noqa: E402
from test_round_driver_advance import adapters  # noqa: E402,F401  (fixture, re-exported)

# `test_round_driver` and `test_round_driver_advance` each load their own copy of the driver; a
# session driven through one is read and written through that same copy.
RDT = TRD.RD
RDA = ADV.RD

_FINDING = {"title": "bug", "severity": "Important", "file": "f.py", "line": 1,
            "consequence": "a reviewer-found defect stays in the change"}


class _AtSynthesis(Exception):
    """Raised by the responder when the driver offers the synthesis step."""


def _drive(tmp_path, verdict, stop_at_synthesis=False, findings=None, **cfg_kw):
    """Drive next/submit with the given findings (default one) on a seatable synthesis cell (or the
    `cfg_kw` cell); returns (session dir, the phases offered). With `stop_at_synthesis` the drive halts
    the moment synthesis is offered."""
    session_dir = str(tmp_path)
    seen = []
    base = TRD._responder(round1_findings=findings or [dict(_FINDING)], verdict=verdict)

    def respond(phase, payload, rnd):
        seen.append(phase)
        if phase == RDT.P_SYNTHESIS and stop_at_synthesis:
            raise _AtSynthesis()
        art = base(phase, payload, rnd)
        if phase == RDT.P_VERIFIERS:
            ok, state = RDT.load_state(session_dir)
            art = dict(art, verifierVendor=RDT._nonpanel_selection(state, session_dir, phase)[0])
        return art

    cfg = S1858._cfg(**cfg_kw)
    cfg.pop("repoRoot")  # the driven session runs in a real checkout
    try:
        TRD._drive_cli(session_dir, TRD._cfg(**cfg), respond)
    except _AtSynthesis:
        pass
    return session_dir, seen


def test_t1_a_panel_with_no_findings_folds_synthesis_and_converges_on_advance(tmp_path, adapters):
    # axis: a round with no survivors emits no synthesis order and folds to its terminal (E2)
    gitdir = ADV._gitdir(tmp_path)
    git = ADV._fake_git(gitdir)
    d = ADV._session(tmp_path, **ADV.SYNTHESIS_SEATABLE)
    ADV._record_all_panel_seats(d)
    out = RDA.cmd_advance(d, git=git)
    assert out["ok"], out
    out = RDA.cmd_advance(d, git=git)  # the verifier fold: empty roster, no survivors
    assert out["ok"] is True, out
    assert out["terminal"] == "converged", out
    assert os.path.isfile(os.path.join(d, RDA.RECEIPT_FILE))
    state = ADV._state(d)
    assert (state["pending"] or {}).get("phase") != RDA.P_SYNTHESIS, state["pending"]
    assert any(e["kind"] == "synthesis-no-survivors" for e in state["decisions"]), state["decisions"]


def test_t2_a_round_whose_every_finding_is_refuted_never_offers_synthesis(tmp_path):
    # axis: a round with no survivors emits no synthesis order and folds to its next step (E1)
    session_dir, seen = _drive(tmp_path, "REFUTED")
    ok, state = RDT.load_state(session_dir)
    assert ok and state["terminal"], state.get("terminal")
    assert RDT.P_SYNTHESIS not in seen, seen
    kinds = [d["kind"] for d in state["decisions"]]
    assert "synthesis-no-survivors" in kinds, kinds
    ledger = {RDT.session_contract.finding_identity_key(e): e
              for e in state[RDT.session_contract.DISPOSITION_LEDGER_KEY]}
    assert [e["disposition"] for e in ledger.values()] == ["refuted"], ledger
    assert RDT.build_receipt(state)


def test_t2b_a_refuted_round_on_an_unseatable_synthesis_cell_records_the_skip_not_the_unseatable_gate(
        tmp_path):
    # axis: the zero-survivor skip sits before the unseatable branch — it records no `synthesisUnseatable` (E6)
    session_dir, seen = _drive(tmp_path, "REFUTED", **S1858._VERIFIER_ONLY)
    ok, state = RDT.load_state(session_dir)
    assert ok and state["terminal"], state.get("terminal")
    # the cell really is unseatable: had survivors existed, the unseatable branch would have claimed it
    assert RDT._nonpanel_unseatable(state, session_dir, RDT.P_SYNTHESIS) is True
    assert RDT.P_SYNTHESIS not in seen, seen
    kinds = [d["kind"] for d in state["decisions"]]
    assert "synthesis-no-survivors" in kinds, kinds
    assert "synthesis-unseatable" not in kinds, kinds
    assert "synthesisUnseatable" not in state["rounds"]["1"], state["rounds"]["1"]


def test_t3_an_empty_grouping_over_survivors_is_accepted_and_keeps_every_survivor(tmp_path):
    # axis: a round with survivors still offers synthesis; a hand empty grouping merges nothing and drops nothing (E3, E4)
    second = dict(_FINDING, title="other bug", line=2)
    session_dir, seen = _drive(tmp_path, "CONFIRMED", stop_at_synthesis=True,
                               findings=[dict(_FINDING), second])
    assert seen[-1] == RDT.P_SYNTHESIS, seen
    ok, state = RDT.load_state(session_dir)
    assert ok and state["pending"]["phase"] == RDT.P_SYNTHESIS
    assert len(state["_verified"]) == 2, state["_verified"]
    out = RDT.cmd_submit(session_dir, RDT.P_SYNTHESIS, state["pending"]["attempt"],
                         RDT.state_hash(state), {"grouping": []})
    assert out["ok"] is True, out
    ok, after = RDT.load_state(session_dir)
    assert ok
    assert sorted(f["title"] for f in after["findings"]) == ["bug", "other bug"], after["findings"]
    assert after["rounds"]["1"]["merges"] == [], after["rounds"]["1"]
    ledger = after[RDT.session_contract.DISPOSITION_LEDGER_KEY]
    sc = RDT.session_contract
    assert not [e for e in ledger if e.get(sc.MERGED_INTO_FIELD) or e.get("disposition") == "refuted"], ledger


def test_t4_a_durable_empty_grouping_without_execution_evidence_is_refused():
    # axis: a durable synthesis landing counts only with runner execution evidence, survivors or not (E5)
    state = S1858._state()
    state["_verified"] = [dict(_FINDING, verdict="CONFIRMED")]
    env = P17._finder_envelope(RA.SEAT_SYNTHESIS)  # no executionEvidence
    env["payload"] = {"grouping": []}
    art, why = RA.assemble(RDT.P_SYNTHESIS, [env], state, state["config"],
                           orders_manifest=P17._finder_manifest(RA.SEAT_SYNTHESIS, vendor="claude"))
    assert art is None, (art, why)
    assert why.startswith("missing-seat-refuse-fold:%s" % RA.SEAT_SYNTHESIS), why
    assert ":unauthenticated-vendor:" in why, why
