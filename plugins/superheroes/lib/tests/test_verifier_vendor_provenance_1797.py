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


# --- the durable path: the executed vendor is the stored envelope's execution evidence ---------------

import pytest  # noqa: E402

import round_adapters  # noqa: E402
import test_round_driver_integration as IT  # noqa: E402


def _drive_verifiers_with_source(tmp_path, monkeypatch, source, name):
    """record-result + advance a REFUTED verdict whose stored envelope's execution evidence names
    ``source`` (fixer claude, so codex is the selected verifier vendor). -> (state, pre_state)."""
    session_dir, gitdir, head_path = IT._bootstrap(tmp_path, name=name)
    findings = [IT._blocking_finding("unchecked index", 2)]
    IT._drive_to_phase(session_dir, gitdir, findings, head_path, RD.P_VERIFIERS)
    state = IT._state(session_dir)
    assert RD._nonpanel_selection(state, session_dir)[0] == "codex"
    pend = state["pending"]
    roster, reason = round_adapters.roster_for(RD.P_VERIFIERS, state, state.get("config") or {})
    assert reason is None and roster, (roster, reason)
    slots = IT._slots_of(roster)
    IT._write_dispatch_manifest(session_dir, pend, slots, lambda seat: "codex")
    monkeypatch.setattr(IT, "_auditor_vendor_for", lambda _state: (lambda _seat: source))
    for seat, occurrence in slots:
        cluster = IT._cluster_for(pend, seat)
        payload = {"verdicts": [{"id": f["id"], "verdict": "REFUTED", "reason": "intentional",
                                 "evidence": "read %s" % f.get("file")}
                                for f in cluster.get("findings") or []]}
        IT._land(session_dir, state, pend, seat, payload, occurrence=occurrence)
        out = IT._record(session_dir, seat, occurrence=occurrence)
        assert out["ok"], out
    out = RD.cmd_advance(session_dir, git=IT._fake_git(gitdir))
    assert out["ok"], out
    assert out["folded"]["phase"] == RD.P_VERIFIERS, out
    return IT._state(session_dir)


def _provenance(state):
    return state["rounds"]["1"]["verifierProvenance"][-1]


def test_a_verdict_executed_by_the_selected_vendor_applies_through_advance(tmp_path, monkeypatch):
    # axis: the executed vendor comes from the stored envelope's execution evidence, not the selection
    state = _drive_verifiers_with_source(tmp_path, monkeypatch, "codex", "exec-selected")
    assert _provenance(state) == {"expected": "codex", "ran": "codex", "outcome": "verdicts-folded"}
    assert state["rounds"]["1"]["verify"]["drops"], "the REFUTED verdict from the selected vendor must clear"


def test_a_verdict_executed_by_the_maker_vendor_is_ignored_through_advance(tmp_path, monkeypatch):
    # axis: stamping the selection as the executed vendor would record codex/folded here and fail
    state = _drive_verifiers_with_source(tmp_path, monkeypatch, "claude", "exec-maker")
    assert _provenance(state) == {"expected": "codex", "ran": "claude", "outcome": "verdicts-ignored"}
    assert not state["rounds"]["1"]["verify"]["drops"]
    assert state["rounds"]["1"]["verify"]["unverified"]


def test_a_verdict_with_no_execution_evidence_is_ignored_through_advance(tmp_path, monkeypatch):
    state = _drive_verifiers_with_source(tmp_path, monkeypatch, "runner", "exec-none")
    assert _provenance(state) == {"expected": "codex", "ran": None, "outcome": "verdicts-ignored"}
    assert not state["rounds"]["1"]["verify"]["drops"]
    assert state["rounds"]["1"]["verify"]["unverified"]


def test_a_defaulted_reviewer_replaced_by_independence_still_needs_a_vendor_claim(tmp_path, monkeypatch):
    # v2: the preference read failing keeps vendorSource defaulted, but the maker-family engine was
    # replaced, so a hand-submitted verdict still needs a vendor claim equal to the selection.
    import engine_pref
    monkeypatch.setattr(engine_pref, "load_engine_prefs", lambda _root: {"readError": "boom"})
    state = _state()
    selected, source = RD._nonpanel_selection(state)
    assert selected == "codex" and source == RD.VENDOR_SOURCE_DEFAULTED
    RD._fold_verifiers(state, state["config"], _refuted(state))
    assert len(state["_verified"]) == 1
    assert state["rounds"]["1"]["verifierProvenance"][-1]["outcome"] == "verdicts-ignored"
    state = _state()
    RD._fold_verifiers(state, state["config"], _refuted(state, verifierVendor="codex"))
    assert state["_verified"] == []
    assert state["rounds"]["1"]["verifierProvenance"][-1]["outcome"] == "verdicts-folded"


# --- v5: provenance is judged per verifier cluster, not once for the batch ----------------------------

def _drive_two_clusters(tmp_path, monkeypatch, source_for, name, **cfg_over):
    """Two findings far apart (two clusters); ``source_for(index)`` names each cluster seat's
    execution-evidence source. -> final state."""
    session_dir, gitdir, head_path = IT._bootstrap(tmp_path, name=name, **cfg_over)
    findings = [IT._blocking_finding("unchecked index", 2), dict(IT._blocking_finding("late defect", 2), file=IT.FILES[1])]
    IT._drive_to_phase(session_dir, gitdir, findings, head_path, RD.P_VERIFIERS)
    state = IT._state(session_dir)
    pend = state["pending"]
    roster, reason = round_adapters.roster_for(RD.P_VERIFIERS, state, state.get("config") or {})
    assert reason is None
    slots = IT._slots_of(roster)
    assert len(slots) == 2, slots
    IT._write_dispatch_manifest(session_dir, pend, slots, lambda seat: "codex")
    by_seat = {seat: source_for(i) for i, (seat, _o) in enumerate(slots)}
    monkeypatch.setattr(IT, "_auditor_vendor_for", lambda _state: (lambda seat: by_seat[seat]))
    for seat, occurrence in slots:
        cluster = IT._cluster_for(pend, seat)
        payload = {"verdicts": [{"id": f["id"], "verdict": "REFUTED", "reason": "intentional",
                                 "evidence": "read %s" % f.get("file")}
                                for f in cluster.get("findings") or []]}
        IT._land(session_dir, state, pend, seat, payload, occurrence=occurrence)
        assert IT._record(session_dir, seat, occurrence=occurrence)["ok"]
    out = RD.cmd_advance(session_dir, git=IT._fake_git(gitdir))
    assert out["ok"], out
    return IT._state(session_dir)


def test_a_proven_cluster_folds_while_an_unproven_cluster_is_ignored(tmp_path, monkeypatch):
    # axis: one batch-wide vendor (the joined claim) would void the proven cluster or honor the unproven one
    state = _drive_two_clusters(tmp_path, monkeypatch, lambda i: "codex" if i == 0 else "runner",
                                "two-clusters")
    rec = state["rounds"]["1"]
    assert len(rec["verify"]["drops"]) == 1, rec["verify"]
    assert len(rec["verify"]["unverified"]) == 1
    outcomes = {(p["ran"], p["outcome"]) for p in rec["verifierProvenance"]}
    assert outcomes == {("codex", "verdicts-folded"), (None, "verdicts-ignored")}


def test_a_maker_cluster_does_not_void_a_proven_cluster(tmp_path, monkeypatch):
    state = _drive_two_clusters(tmp_path, monkeypatch, lambda i: "codex" if i == 0 else "claude",
                                "two-clusters-maker")
    rec = state["rounds"]["1"]
    assert len(rec["verify"]["drops"]) == 1
    outcomes = {(p["ran"], p["outcome"]) for p in rec["verifierProvenance"]}
    assert outcomes == {("codex", "verdicts-folded"), ("claude", "verdicts-ignored")}


# --- v1: the fold authenticates against the vendor the dispatch recorded ----------------------------

def _drive_with_preference_change(tmp_path, monkeypatch, source, name):
    import engine_pref
    pref = {"engine": "codex"}
    monkeypatch.setattr(engine_pref, "resolve_engine", lambda _role, _prefs: pref["engine"])
    session_dir, gitdir, head_path = IT._bootstrap(tmp_path, name=name,
                                                   vendors=["claude", "codex", "cursor"])
    IT._drive_to_phase(session_dir, gitdir, [IT._blocking_finding("unchecked index", 2)], head_path,
                       RD.P_VERIFIERS)
    state = IT._state(session_dir)
    assert RD._nonpanel_selection(state, session_dir)[0] == "codex"
    assert RD._recorded_verifier_vendor(state, session_dir) == "codex"
    pref["engine"] = "cursor"   # the owner edits the reviewer preference while verifiers run
    assert RD._nonpanel_selection(state, session_dir)[0] == "cursor"
    pend = state["pending"]
    roster, reason = round_adapters.roster_for(RD.P_VERIFIERS, state, state.get("config") or {})
    assert reason is None
    slots = IT._slots_of(roster)
    IT._write_dispatch_manifest(session_dir, pend, slots, lambda seat: source)
    monkeypatch.setattr(IT, "_auditor_vendor_for", lambda _state: (lambda seat: source))
    for seat, occurrence in slots:
        cluster = IT._cluster_for(pend, seat)
        payload = {"verdicts": [{"id": f["id"], "verdict": "REFUTED", "reason": "intentional",
                                 "evidence": "read x"} for f in cluster.get("findings") or []]}
        IT._land(session_dir, state, pend, seat, payload, occurrence=occurrence)
        assert IT._record(session_dir, seat, occurrence=occurrence)["ok"]
    out = RD.cmd_advance(session_dir, git=IT._fake_git(gitdir))
    assert out["ok"], out
    return IT._state(session_dir)


def test_the_dispatched_vendor_still_folds_after_the_preference_changes(tmp_path, monkeypatch):
    state = _drive_with_preference_change(tmp_path, monkeypatch, "codex", "pref-dispatched")
    assert _provenance(state) == {"expected": "codex", "ran": "codex", "outcome": "verdicts-folded"}
    assert state["rounds"]["1"]["verify"]["drops"]


def test_another_vendor_does_not_fold_after_the_preference_changes(tmp_path, monkeypatch):
    state = _drive_with_preference_change(tmp_path, monkeypatch, "cursor", "pref-other")
    assert _provenance(state) == {"expected": "codex", "ran": "cursor", "outcome": "verdicts-ignored"}
    assert not state["rounds"]["1"]["verify"]["drops"]
