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


def _cell_proof(vendors=("claude", "codex")):
    """A seat map proving the vendors' dispatched non-panel cells (no seats, no host family)."""
    return IT._nonpanel_cell_proof(vendors)


def _state():
    state = RD.new_state({"repoRoot": "/nonexistent-review-project", "vendors": ["claude", "codex"],
                          "fixerVendor": "claude", "seatMap": _cell_proof()})
    state["_toVerify"] = [{"file": "a.py", "line": 1, "title": "defect", "severity": "Important",
                           "consequence": "a reviewer-found defect stays in the change"}]
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
    selected, source = RD._nonpanel_selection(state, None, RD.P_VERIFIERS)
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


def _blocking_finding(title, line):
    return dict(IT._blocking_finding(title, line),
                consequence="a reviewer-found defect stays in the change")


def _drive_verifiers_with_source(tmp_path, monkeypatch, source, name):
    """record-result + advance a REFUTED verdict whose stored envelope's execution evidence names
    ``source`` (fixer claude, so codex is the selected verifier vendor). -> (state, pre_state)."""
    session_dir, gitdir, head_path = IT._bootstrap(tmp_path, name=name)
    findings = [_blocking_finding("unchecked index", 2)]
    IT._drive_to_phase(session_dir, gitdir, findings, head_path, RD.P_VERIFIERS)
    state = IT._state(session_dir)
    assert RD._nonpanel_selection(state, session_dir, RD.P_VERIFIERS)[0] == "codex"
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
    selected, source = RD._nonpanel_selection(state, None, RD.P_VERIFIERS)
    assert selected == "codex" and source == RD.VENDOR_SOURCE_DEFAULTED
    RD._fold_verifiers(state, state["config"], _refuted(state))
    assert len(state["_verified"]) == 1
    assert state["rounds"]["1"]["verifierProvenance"][-1]["outcome"] == "verdicts-ignored"
    state = _state()
    RD._fold_verifiers(state, state["config"], _refuted(state, verifierVendor="codex"))
    assert state["_verified"] == []
    assert state["rounds"]["1"]["verifierProvenance"][-1]["outcome"] == "verdicts-folded"


# --- v5: provenance is judged per verifier cluster, not once for the batch ----------------------------

def _drive_two_clusters(tmp_path, monkeypatch, source_for, name, overlap=False, **cfg_over):
    """Two findings far apart (two clusters); ``source_for(index)`` names each cluster seat's
    execution-evidence source. -> (final state, ids of cluster 0's findings, ids of cluster 1's)."""
    session_dir, gitdir, head_path = IT._bootstrap(tmp_path, name=name, **cfg_over)
    findings = [_blocking_finding("unchecked index", 2), dict(_blocking_finding("late defect", 2), file=IT.FILES[1])]
    IT._drive_to_phase(session_dir, gitdir, findings, head_path, RD.P_VERIFIERS)
    state = IT._state(session_dir)
    pend = state["pending"]
    roster, reason = round_adapters.roster_for(RD.P_VERIFIERS, state, state.get("config") or {})
    assert reason is None
    slots = IT._slots_of(roster)
    assert len(slots) == 2, slots
    IT._write_dispatch_manifest(session_dir, pend, slots, lambda seat: "codex")
    by_seat = {seat: source_for(i) for i, (seat, _o) in enumerate(slots)}
    ids = [[f["id"] for f in IT._cluster_for(pend, seat).get("findings") or []]
           for seat, _o in slots]
    assert len(ids[0]) == 1 and len(ids[1]) == 1 and ids[0] != ids[1], ids
    monkeypatch.setattr(IT, "_auditor_vendor_for", lambda _state: (lambda seat: by_seat[seat]))
    for i, (seat, occurrence) in enumerate(slots):
        supplied = ids[i] + (ids[0] if overlap and i == 1 else [])  # overlap: seat 1 repeats seat 0
        payload = {"verdicts": [{"id": fid, "verdict": "REFUTED", "reason": "intentional",
                                 "evidence": "read %s" % fid} for fid in supplied]}
        IT._land(session_dir, state, pend, seat, payload, occurrence=occurrence)
        assert IT._record(session_dir, seat, occurrence=occurrence)["ok"]
    out = RD.cmd_advance(session_dir, git=IT._fake_git(gitdir))
    assert out["ok"], out
    return IT._state(session_dir), ids[0], ids[1]


def test_a_proven_cluster_folds_while_an_unproven_cluster_is_ignored(tmp_path, monkeypatch):
    # axis: one batch-wide vendor (the joined claim) would void the proven cluster or honor the unproven one
    state, proven_ids, unproven_ids = _drive_two_clusters(
        tmp_path, monkeypatch, lambda i: "codex" if i == 0 else "runner", "two-clusters")
    rec = state["rounds"]["1"]
    # WHICH finding clears matters: a swap of the clusters' vendor entries clears the other one
    assert {d["id"] for d in rec["verify"]["drops"]} == set(proven_ids), rec["verify"]
    assert set(rec["verify"]["unverified"]) == set(unproven_ids), rec["verify"]
    outcomes = {(p["ran"], p["outcome"]) for p in rec["verifierProvenance"]}
    assert outcomes == {("codex", "verdicts-folded"), (None, "verdicts-ignored")}


def test_a_maker_cluster_does_not_void_a_proven_cluster(tmp_path, monkeypatch):
    state, proven_ids, unproven_ids = _drive_two_clusters(
        tmp_path, monkeypatch, lambda i: "codex" if i == 0 else "claude", "two-clusters-maker")
    rec = state["rounds"]["1"]
    assert {d["id"] for d in rec["verify"]["drops"]} == set(proven_ids), rec["verify"]
    assert set(rec["verify"]["unverified"]) == set(unproven_ids), rec["verify"]
    outcomes = {(p["ran"], p["outcome"]) for p in rec["verifierProvenance"]}
    assert outcomes == {("codex", "verdicts-folded"), ("claude", "verdicts-ignored")}


def test_a_maker_seat_repeating_a_proven_id_does_not_void_it(tmp_path, monkeypatch):
    state, proven_ids, unproven_ids = _drive_two_clusters(
        tmp_path, monkeypatch, lambda i: "codex" if i == 0 else "claude", "two-clusters-overlap",
        overlap=True)
    verify = state["rounds"]["1"]["verify"]
    assert {d["id"] for d in verify["drops"]} == set(proven_ids), verify
    assert set(verify["unverified"]) == set(unproven_ids), verify
    assert verify["ambiguous"] == [], verify


# --- v1: the fold authenticates against the vendor the dispatch recorded ----------------------------

def _tamper_emission_manifest(session_dir, state, phase, vendor):
    """Rewrite every seat's vendor in the on-disk orders manifest, leaving the state-mirrored anchor
    (and so the hash it demands) untouched."""
    pend = state["pending"]
    path = RD._orders_manifest_path(session_dir, pend["round"], phase, pend["attempt"])
    manifest, err = RR.read_json(path)
    assert err is None
    for entry in manifest["seats"].values():
        entry["vendor"] = vendor
    RR.atomic_write_json(path, manifest)
    assert RD._anchored_orders_manifest(state, session_dir, pend["round"], phase,
                                        pend["attempt"]) is None
    assert RD._emission_unverifiable(state, session_dir, phase)


def _drive_with_preference_change(tmp_path, monkeypatch, source, name, tamper=None):
    import engine_pref
    pref = {"engine": "codex"}
    monkeypatch.setattr(engine_pref, "resolve_engine", lambda _role, _prefs: pref["engine"])
    session_dir, gitdir, head_path = IT._bootstrap(tmp_path, name=name,
                                                   vendors=["claude", "codex", "cursor"])
    IT._drive_to_phase(session_dir, gitdir, [_blocking_finding("unchecked index", 2)], head_path,
                       RD.P_VERIFIERS)
    state = IT._state(session_dir)
    assert RD._nonpanel_selection(state, session_dir, RD.P_VERIFIERS)[0] == "codex"
    assert RD._recorded_verifier_vendor(state, session_dir) == "codex"
    pref["engine"] = "cursor"   # the owner edits the reviewer preference while verifiers run
    assert RD._nonpanel_selection(state, session_dir, RD.P_VERIFIERS)[0] == "cursor"
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
    if tamper is not None:
        _tamper_emission_manifest(session_dir, IT._state(session_dir), RD.P_VERIFIERS, tamper)
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


# --- #1797 native host-seat verifier: the executed vendor is the driver's own manifest entry ------------

import round_records as RR  # noqa: E402


def _drive_native_verifiers(tmp_path, name, fixer="codex", vendors=("claude", "codex")):
    """A host-seat (file-channel) verifier landing as a BARE payload the driver wraps with the stub it
    emitted — no runner execution evidence. -> (session_dir, state before fold, advance output)."""
    # a native `claude` seat takes the host's family from the seat map: give the session an honest one
    session_dir, gitdir, head_path = IT._bootstrap(
        tmp_path, name=name, fixerVendor=fixer, vendors=list(vendors),
        seatMap={"hostFamily": "anthropic", "nonPanelLiveCellsSource": "synthesized",
                 "nonPanelLiveCells": []})
    IT._drive_to_phase(session_dir, gitdir, [_blocking_finding("unchecked index", 2)], head_path,
                       RD.P_VERIFIERS)
    state = IT._state(session_dir)
    pend = state["pending"]
    roster, reason = round_adapters.roster_for(RD.P_VERIFIERS, state, state.get("config") or {})
    assert reason is None
    for seat, occurrence in IT._slots_of(roster):
        cluster = IT._cluster_for(pend, seat)
        payload = {"verdicts": [{"id": f["id"], "verdict": "REFUTED", "reason": "intentional",
                                 "evidence": "read x"} for f in cluster.get("findings") or []]}
        skey = RR.storage_key(seat, occurrence)
        RR.atomic_write_json(
            RR.bare_payload_path(session_dir, pend["round"], pend["phase"], skey, pend["attempt"]),
            payload)
        assert IT._record(session_dir, seat, occurrence=occurrence)["ok"]
    out = RD.cmd_advance(session_dir, git=IT._fake_git(gitdir))
    return session_dir, state, out


def test_a_native_claude_verdict_folds_with_dispatch_manifest_provenance(tmp_path):
    # codex made the change; claude is the independent verifier on a host seat (no runner evidence)
    session_dir, before, out = _drive_native_verifiers(tmp_path, "native-claude")
    assert RD._nonpanel_selection(before, session_dir, RD.P_VERIFIERS)[0] == "claude"
    assert out["ok"], out
    state = IT._state(session_dir)
    assert _provenance(state) == {"expected": "claude", "ran": "claude",
                                  "outcome": "verdicts-folded", "provenance": "dispatch-manifest"}
    assert state["rounds"]["1"]["verify"]["drops"], "the native verdict must clear its finding"


def test_a_native_seat_whose_manifest_vendor_is_a_maker_family_is_ignored(tmp_path):
    session_dir, before, _out = _drive_native_verifiers(tmp_path, "native-maker")
    pend = before["pending"]
    manifest = RD._anchored_orders_manifest(before, session_dir, pend["round"], pend["phase"],
                                            pend["attempt"])
    assert manifest and all(e["channel"] == "file" for e in manifest["seats"].values())
    roster, _r = round_adapters.roster_for(RD.P_VERIFIERS, before, before["config"])
    envelopes = [RR.read_json(RR.store_path(session_dir, pend["round"], pend["phase"],
                                            RR.storage_key(seat, occ), pend["attempt"]))[0]
                 for seat, occ in IT._slots_of(roster)]
    assert all(e.get("executionEvidence") is None for e in envelopes)

    def assembled(vendor):
        edited = {"seats": {k: dict(v, vendor=vendor) for k, v in manifest["seats"].items()}}
        art, why = round_adapters.assemble(RD.P_VERIFIERS, envelopes, before, before["config"],
                                           orders_manifest=edited)
        assert why is None, why
        return art

    ok = assembled("claude")
    assert set(ok["verifierSeatVendors"].values()) == {"claude"}
    assert set(ok["verifierSeatProvenance"].values()) == {"dispatch-manifest"}
    for maker in ("codex",):   # the fixer's own vendor: never a verifier
        art = assembled(maker)
        assert set(art["verifierSeatVendors"].values()) == {""}, art
        assert "verifierSeatProvenance" not in art


def test_a_runner_channel_seat_without_evidence_is_still_ignored(tmp_path):
    session_dir, before, _out = _drive_native_verifiers(tmp_path, "native-runner")
    pend = before["pending"]
    manifest = RD._anchored_orders_manifest(before, session_dir, pend["round"], pend["phase"],
                                            pend["attempt"])
    roster, _r = round_adapters.roster_for(RD.P_VERIFIERS, before, before["config"])
    envelopes = [RR.read_json(RR.store_path(session_dir, pend["round"], pend["phase"],
                                            RR.storage_key(seat, occ), pend["attempt"]))[0]
                 for seat, occ in IT._slots_of(roster)]
    runner = {"seats": {k: dict(v, channel="stdout", vendor="cursor")
                        for k, v in manifest["seats"].items()}}
    art, why = round_adapters.assemble(RD.P_VERIFIERS, envelopes, before, before["config"],
                                       orders_manifest=runner)
    assert why is None
    assert set(art["verifierSeatVendors"].values()) == {""}, art


# --- #1797 seams-check / scoped finder: the executed vendor must be the vendor recorded at emission ------

def _finder_envelope(seat, source=None, wrapped=False, schema_over=None):
    env = {"schema": RR.SEAT_RESULT_SCHEMA_V2, "seat": seat, "attempt": 0, "vendor": "codex",
           "model": "m", "payload": {"findings": []}, "provenance": RR.PROVENANCE_DISPATCH_OBSERVED}
    if source is not None:
        env["executionEvidence"] = {"source": source}
    if wrapped:
        env["payloadHashSource"] = "driver-computed"
    return env


def _finder_state():
    return RD.new_state({"repoRoot": "/nonexistent-review-project", "vendors": ["claude", "codex"],
                         "fixerVendor": "claude", "seatMap": _cell_proof()})


def _finder_manifest(seat, channel="stdout", vendor="codex"):
    return {"seats": {RR.storage_key(seat, 0): {"vendor": vendor, "channel": channel}}}


@pytest.mark.parametrize("phase,seat", [(RD.P_SEAMS, round_adapters.SEAT_SEAMS),
                                        (RD.P_SCOPED, round_adapters.SEAT_SCOPED)])
def test_a_finder_executed_by_the_maker_family_does_not_count_as_run(phase, seat):
    state = _finder_state()
    art, why = round_adapters.assemble(phase, [_finder_envelope(seat, source="claude")], state,
                                       state["config"], orders_manifest=_finder_manifest(seat))
    assert art is None and why.startswith("missing-seat-refuse-fold:%s" % seat), (art, why)
    assert "executed=claude" in why and "recorded=codex" in why


@pytest.mark.parametrize("phase,seat", [(RD.P_SEAMS, round_adapters.SEAT_SEAMS),
                                        (RD.P_SCOPED, round_adapters.SEAT_SCOPED)])
def test_a_finder_executed_by_the_recorded_vendor_counts_as_run(phase, seat):
    state = _finder_state()
    art, why = round_adapters.assemble(phase, [_finder_envelope(seat, source="codex")], state,
                                       state["config"], orders_manifest=_finder_manifest(seat))
    assert why is None and art["findings"] == []


@pytest.mark.parametrize("phase,seat", [(RD.P_SEAMS, round_adapters.SEAT_SEAMS),
                                        (RD.P_SCOPED, round_adapters.SEAT_SCOPED)])
def test_a_driver_wrapped_host_seat_finder_authenticates_by_its_manifest_vendor(phase, seat):
    state = _finder_state()
    env = _finder_envelope(seat, wrapped=True)
    art, why = round_adapters.assemble(phase, [env], state, state["config"],
                                       orders_manifest=_finder_manifest(seat, channel="file"))
    assert why is None and art["provenance"]["provenanceSource"] == {seat: "dispatch-manifest"}
    # the same landing on a runner-channel seat, or with an evidence-less hand-landed envelope: not run
    for bad in (_finder_manifest(seat, channel="stdout"),):
        art, why = round_adapters.assemble(phase, [env], state, state["config"], orders_manifest=bad)
        assert art is None and why.startswith("missing-seat-refuse-fold"), (art, why)
    art, why = round_adapters.assemble(phase, [_finder_envelope(seat)], state, state["config"],
                                       orders_manifest=_finder_manifest(seat, channel="file"))
    assert art is None and why.startswith("missing-seat-refuse-fold"), (art, why)


def test_a_hand_submitted_finder_needs_the_recorded_vendor_claim(tmp_path):
    state = _state()
    fault = RD._finder_hand_claim_fault
    assert fault(state, None, RD.P_SEAMS, {"findings": []}) is not None
    assert fault(state, None, RD.P_SEAMS, {"findings": [], "reviewerVendor": "claude"}) is not None
    assert fault(state, None, RD.P_SCOPED, {"findings": [], "reviewerVendor": "codex"}) is None


def _drive_scoped_with_source(tmp_path, monkeypatch, source, name):
    session_dir, gitdir, head_path = IT._bootstrap(tmp_path, name=name)
    IT._drive_to_phase(session_dir, gitdir, [_blocking_finding("unchecked index", 2)], head_path,
                       RD.P_SCOPED)
    state = IT._state(session_dir)
    assert RD._nonpanel_selection(state, session_dir, RD.P_SCOPED)[0] == "codex"
    pend = state["pending"]
    monkeypatch.setattr(IT, "_auditor_vendor_for", lambda _state: (lambda _seat: source))
    IT._land(session_dir, state, pend, round_adapters.SEAT_SCOPED, {"findings": []})
    assert IT._record(session_dir, round_adapters.SEAT_SCOPED)["ok"]
    return session_dir, RD.cmd_advance(session_dir, git=IT._fake_git(gitdir))


def test_a_maker_executed_scoped_finder_does_not_converge_the_round_through_advance(tmp_path, monkeypatch):
    session_dir, out = _drive_scoped_with_source(tmp_path, monkeypatch, "claude", "scoped-maker")
    assert out["ok"] is False and out["reason"] == "assemble-refused", out
    assert "unauthenticated-vendor" in out["detail"]
    state = IT._state(session_dir)
    assert not state.get("terminal") and state["pending"]["phase"] == RD.P_SCOPED


def test_a_recorded_vendor_scoped_finder_folds_through_advance(tmp_path, monkeypatch):
    _session_dir, out = _drive_scoped_with_source(tmp_path, monkeypatch, "codex", "scoped-codex")
    assert out["ok"] is True and out["folded"]["phase"] == RD.P_SCOPED, out


# --- fail closed: an emission whose manifest cannot verify authenticates nothing --------------------------

def test_verdicts_are_ignored_when_the_anchored_manifest_is_tampered(tmp_path, monkeypatch):
    # the preference moved to cursor, so the live selection would accept a cursor verdict; the
    # tampered manifest (anchor intact) must not release that fallback
    state = _drive_with_preference_change(tmp_path, monkeypatch, "cursor", "pref-tampered",
                                          tamper="cursor")
    # Per-seat binding: the unverifiable manifest reaches the adapter as `{}`, which assigns no seat any
    # id, so every verdict is dropped as unordered BEFORE the fold sees it (the fold's own
    # `emission-manifest-unverifiable` row is therefore no longer reachable on this path; it stays
    # asserted directly by `test_nonpanel_provenance_1851::test_mixed_manifest_verifier_verdicts_fold_as_silence`).
    assert not state["rounds"]["1"].get("verifierProvenance")
    assert not state["rounds"]["1"]["verify"]["drops"]
    assert state["rounds"]["1"]["verify"]["unverified"]
    unordered = state["rounds"]["1"]["adapterProvenance"]["byPhase"][RD.P_VERIFIERS]["unorderedVerdicts"]
    assert unordered and all(entry["orderedTo"] is None for entry in unordered), unordered


def test_a_hand_artifact_cannot_supply_its_own_per_seat_provenance(tmp_path):
    # maker (claude) claims verifierVendor, while its own courier map says codex ran the seat
    session_dir, state = _hand_verifier_session(tmp_path, "hand-seat-map")
    staged = V.stage_ids(state["_toVerify"])
    artifact = {"verdicts": [{"id": s["id"], "verdict": "REFUTED", "reason": "intentional"}
                             for s in staged],
                "verifierVendor": "claude",
                "verifierSeatVendors": {s["id"]: "codex" for s in staged}}
    out = RD.cmd_submit(session_dir, RD.P_VERIFIERS, state["pending"]["attempt"],
                        RD.state_hash(state), artifact)
    assert out["ok"], out
    after = IT._state(session_dir)
    assert not after["rounds"][str(state["round"])]["verify"]["drops"]
    assert after["rounds"][str(state["round"])]["verifierProvenance"][-1]["outcome"] == "verdicts-ignored"


def _hand_verifier_session(tmp_path, name):
    session_dir, gitdir, head_path = IT._bootstrap(tmp_path, name=name)
    IT._drive_to_phase(session_dir, gitdir, [_blocking_finding("unchecked index", 2)], head_path,
                       RD.P_VERIFIERS)
    state = IT._state(session_dir)
    state.pop("_advanceUsed", None)  # the same session, now answered by hand
    RD.save_state(session_dir, state)
    assert RD._nonpanel_selection(state, session_dir, RD.P_VERIFIERS)[0] == "codex"
    return session_dir, state


def _drive_scoped_tampered(tmp_path, monkeypatch, name, tamper):
    session_dir, gitdir, head_path = IT._bootstrap(
        tmp_path, name=name, vendors=["claude", "codex", "cursor"], seatMap=_cell_proof(("claude", "codex", "cursor")))
    IT._drive_to_phase(session_dir, gitdir, [_blocking_finding("unchecked index", 2)], head_path,
                       RD.P_SCOPED)
    state = IT._state(session_dir)
    assert RD._nonpanel_selection(state, session_dir, RD.P_SCOPED)[0] == "codex"
    monkeypatch.setattr(IT, "_auditor_vendor_for", lambda _state: (lambda _seat: "cursor"))
    IT._land(session_dir, state, state["pending"], round_adapters.SEAT_SCOPED, {"findings": []})
    assert IT._record(session_dir, round_adapters.SEAT_SCOPED)["ok"]
    if tamper:
        _tamper_emission_manifest(session_dir, IT._state(session_dir), RD.P_SCOPED, "cursor")
    return session_dir, RD.cmd_advance(session_dir, git=IT._fake_git(gitdir))


@pytest.mark.parametrize("tamper", [False, True])
def test_a_tampered_manifest_cannot_authenticate_an_unordered_finder(tmp_path, monkeypatch, tamper):
    # codex was ordered; cursor ran. Rewriting the manifest to say cursor (anchor still in place)
    # must not turn that into a recorded vendor: same refusal as the untampered control.
    session_dir, out = _drive_scoped_tampered(tmp_path, monkeypatch, "scoped-tamper-%s" % tamper, tamper)
    assert out["ok"] is False and out["reason"] == "assemble-refused", out
    state = IT._state(session_dir)
    assert not state.get("terminal") and state["pending"]["phase"] == RD.P_SCOPED


def test_finder_hand_submit_is_authenticated_through_the_submit_path(tmp_path):
    session_dir, gitdir, head_path = IT._bootstrap(tmp_path, name="hand-finder")
    IT._drive_to_phase(session_dir, gitdir, [_blocking_finding("unchecked index", 2)], head_path,
                       RD.P_SCOPED)
    state = IT._state(session_dir)
    state.pop("_advanceUsed", None)
    RD.save_state(session_dir, state)
    attempt = state["pending"]["attempt"]
    for bad in ({"findings": []}, {"findings": [], "reviewerVendor": "claude"}):
        state = IT._state(session_dir)
        out = RD.cmd_submit(session_dir, RD.P_SCOPED, attempt, RD.state_hash(state), bad)
        assert out["ok"] is False and out["reason"] == "nonpanel-reviewer-unauthenticated", out
        assert IT._state(session_dir)["pending"]["phase"] == RD.P_SCOPED
    state = IT._state(session_dir)
    out = RD.cmd_submit(session_dir, RD.P_SCOPED, attempt, RD.state_hash(state),
                        {"findings": [], "reviewerVendor": "codex"})
    assert out["ok"] is True, out
