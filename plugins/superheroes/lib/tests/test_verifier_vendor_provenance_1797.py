"""#1797 — the verifier fold counts verdicts only from the vendor the driver selected outside the
makers' families; the manifest names that vendor for the dispatch, and the fold records it."""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import round_driver as RD  # noqa: E402
import verification as V  # noqa: E402


def _state():
    state = RD.new_state({"repoRoot": "/nonexistent-review-project", "vendors": ["claude", "codex"],
                          "fixerVendor": "claude"})
    state["_toVerify"] = [{"file": "a.py", "line": 1, "title": "defect", "severity": "Important"}]
    return state


def _refuted(state, **extra):
    fid = V.stage_ids(state["_toVerify"])[0]["id"]
    artifact = {"verdicts": [{"id": fid, "verdict": "REFUTED", "reason": "intentional"}]}
    artifact.update(extra)
    return artifact


def test_the_transport_row_carries_the_selected_vendor(tmp_path):
    state = _state()
    row = RD._seat_transport_row(state, RD.P_VERIFIERS, "verifier:c1", 0, state["config"], {},
                                 str(tmp_path))
    assert row["vendor"] == "codex"
    assert row["vendorSource"] == RD.VENDOR_SOURCE_INDEPENDENT


def test_a_refuted_verdict_without_a_vendor_claim_does_not_clear_the_finding():
    # axis: a replaced (independent) selection needs the verifier's vendor before a REFUTED verdict counts
    state = _state()
    selected, source = RD._nonpanel_selection(state)
    assert selected == "codex" and source == RD.VENDOR_SOURCE_INDEPENDENT
    RD._fold_verifiers(state, state["config"], _refuted(state))
    assert len(state["_verified"]) == 1
    assert state["rounds"]["1"]["verifierProvenance"][-1]["outcome"] == "verdicts-ignored"


def test_a_refuted_verdict_from_the_maker_family_does_not_clear_the_finding():
    state = _state()
    RD._fold_verifiers(state, state["config"], _refuted(state, verifierVendor="claude"))
    assert len(state["_verified"]) == 1
    assert state["rounds"]["1"]["verifierProvenance"][-1] == {
        "expected": "codex", "ran": "claude", "outcome": "verdicts-ignored"}


def test_a_refuted_verdict_from_the_selected_vendor_clears_and_records_the_vendor():
    state = _state()
    RD._fold_verifiers(state, state["config"], _refuted(state, verifierVendor="codex"))
    assert state["_verified"] == []
    assert state["rounds"]["1"]["verifierProvenance"][-1] == {
        "expected": "codex", "ran": "codex", "outcome": "verdicts-folded"}


def test_the_verifier_contract_accepts_the_vendor_field():
    assert RD.verifier_results_fault(_refuted(_state(), verifierVendor="codex")) is None
