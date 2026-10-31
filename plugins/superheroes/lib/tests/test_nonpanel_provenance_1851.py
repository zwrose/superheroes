"""#1851 (review C5 L4) K — a non-panel result counts only when the vendor that ran it is the vendor its
order named AND that vendor passes the shared eligibility bar (`round_adapters._maker_barred`).

Covers the verifier (per seat and on a hand claim), the gap sweep and the scoped finder on the advance
path, the hand `submit` path and the library `run_loop` path.

Bite-proof record: plugins/superheroes/lib/tests/bite_proofs/wo_1b_1851_nonpanel_provenance.md
"""
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import round_adapters as RA  # noqa: E402
import round_driver as RD  # noqa: E402
import round_records as RR  # noqa: E402
import verification as V  # noqa: E402
import test_round_driver as TRD  # noqa: E402
import test_round_driver_integration as IT  # noqa: E402
import test_verifier_vendor_provenance_1797 as P17  # noqa: E402

FINDERS = [(RD.P_GAPSWEEP, RA.SEAT_GAPSWEEP), (RD.P_SCOPED, RA.SEAT_SCOPED)]
BAR_HOW = ["maker-family", "vendor-is-the-fixer"]


def _state(fixer="claude", host="anthropic", makers=()):
    """A session whose independent selection is `codex` (fixer `claude`, codex outranks cursor)."""
    seat_map = {"hostFamily": host, **TRD._nonpanel_cell_proof(["claude", "codex", "cursor"])}
    if makers:
        seat_map["makerFamilies"] = list(makers)
    state = RD.new_state({"repoRoot": "/nonexistent-review-project", "vendors": ["claude", "codex", "cursor"],
                          "fixerVendor": fixer, "seatMap": seat_map})
    state["_toVerify"] = [{"file": "a.py", "line": 1, "title": "defect", "severity": "Important"}]
    return state


def _bar_codex(state, how):
    """After `codex` was recorded at emission, make it ineligible: a maker family or the fixer's own vendor."""
    if how == "maker-family":
        state["config"]["seatMap"]["makerFamilies"] = ["openai"]
    else:
        state["config"]["fixerVendor"] = "codex"
    assert RA._maker_barred(state, state["config"])("codex")


def _emit(state, session_dir, phase, vendor, attempt=0, channel="stdout"):
    """Record an emission as the driver does: an orders manifest on disk plus its state-mirrored anchor."""
    session_dir = str(session_dir)
    seats = RA.roster_for(phase, state, state["config"])[0]
    manifest = {"seats": {RR.storage_key(seat, 0): {"vendor": vendor, "channel": channel} for seat in seats}}
    RR.atomic_write_json(RD._orders_manifest_path(session_dir, state["round"], phase, attempt), manifest)
    state.setdefault("_ordersAnchors", {})[RD._anchor_key(state["round"], phase, attempt)] = {
        "manifestSha256": RR.sha256_text(RR.canonical(manifest))}
    return manifest


def _verdicts(state):
    return [{"id": s["id"], "verdict": "REFUTED", "reason": "intentional"} for s in V.stage_ids(state["_toVerify"])]


def _seat_artifact(state, ran):
    """The adapter's durable verifier artifact: each verdict id -> the vendor that ran its seat."""
    verdicts = _verdicts(state)
    return {"verdicts": verdicts, "verifierVendor": ran, "verifierSeatVendors": {v["id"]: ran for v in verdicts}}


def _fold(state, session_dir, artifact):
    RD._fold_verifiers(state, state["config"], artifact, session_dir=str(session_dir))
    return state["rounds"]["1"]["verifierProvenance"][-1], len(state["_verified"])


def _assemble_finder(state, phase, seat, source, recorded, **env):
    manifest = {"seats": {RR.storage_key(seat, 0): {"vendor": recorded, "channel": env.pop("channel", "stdout")}}}
    return RA.assemble(phase, [P17._finder_envelope(seat, source=source, **env)], state, state["config"],
                       orders_manifest=manifest)


# --- T1: the executed vendor differs from the vendor the order named -----------------------------------

def test_t1_advance_verifier_executed_other_than_recorded_is_ignored(tmp_path):
    # axis: per-seat equality against the vendor recorded at emission (P7)
    state = _state()
    _emit(state, tmp_path, RD.P_VERIFIERS, "codex")
    row, unverified = _fold(state, tmp_path, _seat_artifact(state, "cursor"))
    assert row == {"expected": "codex", "ran": "cursor", "outcome": "verdicts-ignored"}
    assert unverified == 1 and not state["rounds"]["1"]["verify"]["drops"]


def test_t1_advance_verifier_positive_control_recorded_vendor_folds(tmp_path):
    state = _state()
    _emit(state, tmp_path, RD.P_VERIFIERS, "codex")
    row, unverified = _fold(state, tmp_path, _seat_artifact(state, "codex"))
    assert row == {"expected": "codex", "ran": "codex", "outcome": "verdicts-folded"}
    assert unverified == 0 and state["rounds"]["1"]["verify"]["drops"]


@pytest.mark.parametrize("phase,seat", FINDERS)
def test_t1_advance_finder_executed_other_than_recorded_is_refused(phase, seat):
    # axis: the finder authentication compares the executed vendor with the recorded one (P6)
    art, why = _assemble_finder(_state(), phase, seat, "cursor", "codex")
    assert art is None and why.startswith("missing-seat-refuse-fold:%s" % seat), (art, why)
    assert "executed=cursor" in why and "recorded=codex" in why and "vendor-ineligible" not in why


@pytest.mark.parametrize("phase,seat", FINDERS)
def test_t1_advance_finder_positive_control_recorded_vendor_counts(phase, seat):
    art, why = _assemble_finder(_state(), phase, seat, "codex", "codex")
    assert why is None and art["findings"] == []


def test_t1_hand_verifier_claim_other_than_recorded_is_ignored(tmp_path):
    state = _state()
    _emit(state, tmp_path, RD.P_VERIFIERS, "codex")
    row, unverified = _fold(state, tmp_path, {"verdicts": _verdicts(state), "verifierVendor": "cursor"})
    assert row == {"expected": "codex", "ran": "cursor", "outcome": "verdicts-ignored"}
    assert unverified == 1


@pytest.mark.parametrize("phase,seat", FINDERS)
def test_t1_hand_finder_claim_other_than_recorded_is_refused(tmp_path, phase, seat):
    # axis: the hand claim must equal the vendor recorded at emission (P8)
    state = _state()
    _emit(state, tmp_path, phase, "codex")
    fault = RD._finder_hand_claim_fault(state, str(tmp_path), phase, {"findings": [], "reviewerVendor": "cursor"})
    assert fault is not None and "'cursor'" in fault and "recorded 'codex'" in fault, fault
    assert RD._finder_hand_claim_fault(state, str(tmp_path), phase,
                                       {"findings": [], "reviewerVendor": "codex"}) is None


def test_t1_library_finder_reporting_another_vendor_is_unauthenticated():
    state = _state()
    assert RD._nonpanel_selection(state, None, RD.P_GAPSWEEP)[0] == "codex"
    assert RD._library_finder_unauthenticated(state, "cursor", RD.P_GAPSWEEP) is True
    assert RD._library_finder_unauthenticated(state, "codex", RD.P_GAPSWEEP) is False


# --- T2: the executed vendor equals the order's but sits in a maker family / is the fixer --------------

@pytest.mark.parametrize("how", BAR_HOW)
def test_t2_advance_verifier_ineligible_recorded_vendor_is_ignored(tmp_path, how):
    # axis: (b) on the per-seat branch — equal to the recorded vendor is not enough (P3)
    state = _state()
    _emit(state, tmp_path, RD.P_VERIFIERS, "codex")
    _bar_codex(state, how)
    row, unverified = _fold(state, tmp_path, _seat_artifact(state, "codex"))
    assert row == {"expected": "codex", "ran": "codex", "outcome": "verdicts-ignored",
                   "reason": "vendor-ineligible"}
    assert unverified == 1 and not state["rounds"]["1"]["verify"]["drops"]


@pytest.mark.parametrize("how", BAR_HOW)
@pytest.mark.parametrize("phase,seat", FINDERS)
def test_t2_advance_finder_ineligible_recorded_vendor_is_refused(phase, seat, how):
    # axis: (b) in the finder authentication — executed == recorded is not enough (P2)
    state = _state()
    _bar_codex(state, how)
    art, why = _assemble_finder(state, phase, seat, "codex", "codex")
    assert art is None and why.startswith("missing-seat-refuse-fold:%s" % seat), (art, why)
    assert why.endswith("executed=codex:recorded=codex:vendor-ineligible"), why


@pytest.mark.parametrize("how", BAR_HOW)
def test_t2_hand_verifier_ineligible_recorded_vendor_claim_is_ignored(tmp_path, how):
    # axis: (b) on the hand claim branch (P3)
    state = _state()
    _emit(state, tmp_path, RD.P_VERIFIERS, "codex")
    _bar_codex(state, how)
    row, unverified = _fold(state, tmp_path, {"verdicts": _verdicts(state), "verifierVendor": "codex"})
    assert row == {"expected": "codex", "ran": "codex", "outcome": "verdicts-ignored",
                   "reason": "vendor-ineligible"}
    assert unverified == 1


@pytest.mark.parametrize("how", BAR_HOW)
@pytest.mark.parametrize("phase,seat", FINDERS)
def test_t2_hand_finder_ineligible_recorded_vendor_claim_is_refused(tmp_path, phase, seat, how):
    # axis: (b) in the hand finder claim check (P4)
    state = _state()
    _emit(state, tmp_path, phase, "codex")
    claim = {"findings": [], "reviewerVendor": "codex"}
    assert RD._finder_hand_claim_fault(state, str(tmp_path), phase, claim) is None
    _bar_codex(state, how)
    fault = RD._finder_hand_claim_fault(state, str(tmp_path), phase, claim)
    assert fault is not None and "ineligible" in fault, fault


def _library_run(reported):
    """run_loop over a big diff so a gap sweep runs; `reported` is what the gap-sweep callback returns."""
    calls = {"gap": 0}

    def reviewer(dim, tier, rnd, ctx):
        if dim == "gap-sweep":
            calls["gap"] += 1
            return reported
        return []

    seams = TRD._seams(vendors=["claude", "codex"])
    # the callback reports (or not) exactly what the test says
    seams["reviewer"] = reviewer
    _result, state = TRD._run_loop_capturing_state(seams, TRD._cfg_cert(diff=TRD._big_diff(25)))
    return state, calls["gap"]


def _parked(state):
    return state.get("terminal") == "cannot-certify" and \
        str(state["certification"]["reason"]).startswith("nonpanel-finder-unauthenticated:%s" % RD.P_GAPSWEEP)


@pytest.mark.parametrize("reported", [
    pytest.param({"findings": [], "vendor": "claude"}, id="maker-vendor"),
    pytest.param({"findings": [], "vendor": "cursor"}, id="other-vendor"),
    pytest.param([], id="nothing-reported-while-the-engine-was-replaced"),
])
def test_t2_library_gap_sweep_that_does_not_authenticate_parks_the_loop(reported):
    # axis: the library finder guard — a result not from the selected eligible vendor never folds (P9)
    state, calls = _library_run(reported)
    assert calls == 1 and _parked(state), (state.get("terminal"), state.get("certification"))


def test_t2_library_gap_sweep_positive_control_selected_vendor_folds():
    state, calls = _library_run({"findings": [], "vendor": "codex"})
    assert calls >= 1 and not _parked(state) and state.get("terminal") != "cannot-certify"


@pytest.mark.parametrize("vendor,parks", [("cursor", True), ("codex", False)])
def test_t2_library_scoped_finder_that_does_not_authenticate_parks_the_loop(vendor, parks):
    # axis: the run_loop guard covers the scoped finder too, not only the gap sweep (P9)
    calls = {"scoped": 0}

    def reviewer(dim, tier, rnd, ctx):
        if dim == "scoped-finder":
            calls["scoped"] += 1
            return {"findings": [], "vendor": vendor}
        if rnd == 1 and dim == "code-reviewer":
            return {"findings": [{"title": "bug", "severity": "Important", "file": "f.py", "line": 1,
                                  "consequence": "a reviewer-found defect stays in the change"}]}
        return []

    def fix_step(batch, rnd, payload):
        return {"fixes": [], "headDiff": TRD.HEAD_NEW_SURFACE, "changedSubjects": ["Code"]}

    _result, state = TRD._run_loop_capturing_state(
        TRD._seams(reviewer=reviewer, fix_step=fix_step, vendors=["claude", "codex"]), TRD._cfg_cert())
    assert calls["scoped"] >= 1
    reason = str((state.get("certification") or {}).get("reason"))
    assert (state.get("terminal") == "cannot-certify"
            and reason.startswith("nonpanel-finder-unauthenticated:%s" % RD.P_SCOPED)) is parks, \
        (state.get("terminal"), reason)
    if parks:
        assert calls["scoped"] == 1


def test_t2_library_unseatable_selection_parks():
    state = _state(makers=["openai", "xai"])
    assert RD._nonpanel_selection(state, None, RD.P_GAPSWEEP) == (None, None)
    assert RD._library_finder_unauthenticated(state, "codex", RD.P_GAPSWEEP) is True
    assert RD._library_finder_unauthenticated(state, None, RD.P_GAPSWEEP) is True


def test_t2_library_selection_that_is_the_engine_folds_without_a_report():
    state = _state(fixer="codex")
    selected, _source = RD._nonpanel_selection(state, None, RD.P_GAPSWEEP)
    assert selected == "claude" and not RD._nonpanel_replaced(state, selected)
    assert RD._library_finder_unauthenticated(state, None, RD.P_GAPSWEEP) is False
    assert RD._library_finder_unauthenticated(state, "claude", RD.P_GAPSWEEP) is False
    assert RD._library_finder_unauthenticated(state, "cursor", RD.P_GAPSWEEP) is True


# --- T3: the hand-submit claim rules -------------------------------------------------------------------

@pytest.mark.parametrize("phase,seat", FINDERS)
def test_t3_missing_claim_when_the_selection_replaced_the_engine_is_refused(tmp_path, phase, seat):
    state = _state()
    assert RD._nonpanel_replaced(state, "codex")
    fault = RD._finder_hand_claim_fault(state, str(tmp_path), phase, {"findings": []})
    assert fault is not None and "carries no `reviewerVendor`" in fault, fault


@pytest.mark.parametrize("phase,seat", FINDERS)
def test_t3_no_emission_leaves_the_live_selection_as_the_expectation(tmp_path, phase, seat):
    state = _state()
    assert RD._latest_emission_attempt(state, str(tmp_path), phase) is None
    assert RD._finder_hand_claim_fault(state, str(tmp_path), phase,
                                       {"findings": [], "reviewerVendor": "codex"}) is None
    assert RD._finder_hand_claim_fault(state, str(tmp_path), phase,
                                       {"findings": [], "reviewerVendor": "cursor"}) is not None


@pytest.mark.parametrize("tamper", ["rewrite", "delete"])
@pytest.mark.parametrize("phase,seat", FINDERS)
def test_t3_claim_on_a_lost_or_tampered_emission_is_refused(tmp_path, phase, seat, tamper):
    # axis: (c) an emission whose manifest no longer verifies authenticates nothing (P5)
    state = _state()
    manifest = _emit(state, tmp_path, phase, "codex")
    claim = {"findings": [], "reviewerVendor": "codex"}
    assert RD._finder_hand_claim_fault(state, str(tmp_path), phase, claim) is None
    path = RD._orders_manifest_path(str(tmp_path), state["round"], phase, 0)
    if tamper == "rewrite":
        for entry in manifest["seats"].values():
            entry["vendor"] = "cursor"
        RR.atomic_write_json(path, manifest)
    else:
        os.remove(path)
    assert RD._emission_unverifiable(state, str(tmp_path), phase)
    fault = RD._finder_hand_claim_fault(state, str(tmp_path), phase, claim)
    assert fault is not None and "does not verify" in fault, fault
    # the tampered manifest names cursor, but no claim for it is released either
    assert RD._finder_hand_claim_fault(state, str(tmp_path), phase,
                                       {"findings": [], "reviewerVendor": "cursor"}) is not None


def test_t3_finder_hand_submit_through_the_submit_path_refuses_a_lost_emission(tmp_path):
    session_dir, gitdir, head_path = IT._bootstrap(tmp_path, name="hand-lost-emission")
    IT._drive_to_phase(session_dir, gitdir, [IT._blocking_finding("unchecked index", 2)], head_path,
                       RD.P_SCOPED)
    state = IT._state(session_dir)
    state.pop("_advanceUsed", None)
    RD.save_state(session_dir, state)
    attempt = state["pending"]["attempt"]
    claim = {"findings": [], "reviewerVendor": "codex"}
    P17._tamper_emission_manifest(session_dir, state, RD.P_SCOPED, "cursor")
    out = RD.cmd_submit(session_dir, RD.P_SCOPED, attempt, RD.state_hash(IT._state(session_dir)), claim)
    assert out["ok"] is False and out["reason"] == "nonpanel-reviewer-unauthenticated", out
    assert "does not verify" in out["detail"]
    assert IT._state(session_dir)["pending"]["phase"] == RD.P_SCOPED


@pytest.mark.parametrize("phase,seat", FINDERS)
def test_t3_recorded_claim_requirement_survives_a_preference_edit(tmp_path, monkeypatch, phase, seat):
    state = _state()
    manifest = _emit(state, tmp_path, phase, "codex")
    manifest["claimRequired"] = True
    RR.atomic_write_json(RD._orders_manifest_path(str(tmp_path), state["round"], phase, 0), manifest)
    state["_ordersAnchors"][RD._anchor_key(state["round"], phase, 0)] = {
        "manifestSha256": RR.sha256_text(RR.canonical(manifest))}
    # the preference is edited: codex is now the configured reviewer, so nothing is replaced
    monkeypatch.setattr(RD, "_reviewer_engine_vendor", lambda _root: ("codex", RD.VENDOR_SOURCE_CONFIGURED))
    assert RD._nonpanel_selection(state, str(tmp_path), phase) == ("codex", RD.VENDOR_SOURCE_CONFIGURED)
    assert not RD._nonpanel_replaced(state, "codex", str(tmp_path))
    fault = RD._finder_hand_claim_fault(state, str(tmp_path), phase, {"findings": []})
    assert fault is not None and "carries no `reviewerVendor`" in fault, fault
    assert RD._finder_hand_claim_fault(state, str(tmp_path), phase,
                                       {"findings": [], "reviewerVendor": "codex"}) is None
    # control: an anchored manifest without `claimRequired` accepts the missing claim
    manifest.pop("claimRequired")
    RR.atomic_write_json(RD._orders_manifest_path(str(tmp_path), state["round"], phase, 0), manifest)
    state["_ordersAnchors"][RD._anchor_key(state["round"], phase, 0)] = {
        "manifestSha256": RR.sha256_text(RR.canonical(manifest))}
    assert RD._finder_hand_claim_fault(state, str(tmp_path), phase, {"findings": []}) is None


@pytest.mark.parametrize("artifact", [None, []])
def test_t3_finder_hand_submit_refuses_a_non_object_artifact(tmp_path, artifact):
    session_dir, gitdir, head_path = IT._bootstrap(tmp_path, name="hand-non-object")
    IT._drive_to_phase(session_dir, gitdir, [IT._blocking_finding("unchecked index", 2)], head_path,
                       RD.P_SCOPED)
    state = IT._state(session_dir)
    state.pop("_advanceUsed", None)
    RD.save_state(session_dir, state)
    out = RD.cmd_submit(session_dir, RD.P_SCOPED, state["pending"]["attempt"],
                        RD.state_hash(IT._state(session_dir)), artifact)
    assert out["ok"] is False and out["reason"] == "nonpanel-reviewer-unauthenticated", out
    assert IT._state(session_dir)["pending"]["phase"] == RD.P_SCOPED


# --- T4: the driver-wrapped native host-seat landing --------------------------------------------------

def _wrapped_verifier_artifact(state, manifest_vendor="claude"):
    seat = RA.roster_for(RD.P_VERIFIERS, state, state["config"])[0][0]
    env = {"schema": RR.SEAT_RESULT_SCHEMA_V2, "seat": seat, "attempt": 0, "vendor": "claude", "model": "m",
           "payload": {"verdicts": [dict(v, evidence="read x") for v in _verdicts(state)]},
           "provenance": RR.PROVENANCE_DISPATCH_OBSERVED, "payloadHashSource": "driver-computed"}
    # the seat's `ids` are what its emitted order assigned it: a verdict counts only from the ordered seat
    manifest = {"seats": {RR.storage_key(seat, 0): {"vendor": manifest_vendor, "channel": "file",
                                                    "ids": [v["id"] for v in _verdicts(state)]}}}
    art, why = RA.assemble(RD.P_VERIFIERS, [env], state, state["config"], orders_manifest=manifest)
    assert why is None, why
    return art


HOSTS = [
    pytest.param({"fixer": "codex", "host": "anthropic"}, True, id="host-known-outside-the-makers"),
    pytest.param({"fixer": "codex", "host": "anthropic", "makers": ["anthropic"]}, False,
                 id="host-family-is-a-maker-family"),
    pytest.param({"fixer": "codex", "host": None}, False, id="host-family-null"),
    pytest.param({"fixer": "codex", "host": ""}, False, id="host-family-empty"),
]


@pytest.mark.parametrize("cfg,trusted", HOSTS)
def test_t4_native_host_seat_verifier_is_trusted_only_for_a_known_non_maker_host(cfg, trusted):
    # axis: the barred predicate reaches the driver-wrapped host-seat manifest path (P10)
    art = _wrapped_verifier_artifact(_state(**cfg))
    assert set(art["verifierSeatVendors"].values()) == ({"claude"} if trusted else {""}), art
    assert ("verifierSeatProvenance" in art) is trusted


@pytest.mark.parametrize("cfg,trusted", HOSTS)
@pytest.mark.parametrize("phase,seat", FINDERS)
def test_t4_native_host_seat_finder_is_trusted_only_for_a_known_non_maker_host(phase, seat, cfg, trusted):
    art, why = _assemble_finder(_state(**cfg), phase, seat, None, "claude", wrapped=True, channel="file")
    if trusted:
        assert why is None and art["provenance"]["provenanceSource"] == {seat: "dispatch-manifest"}
    else:
        assert art is None and why.startswith("missing-seat-refuse-fold:%s" % seat), (art, why)


# --- F1: the shared home of the non-panel eligibility predicate ---------------------------------------

def test_f1_nonpanel_barred_is_the_shared_predicate_and_reads_the_host_family():
    # axis: receipt_disclosures.nonpanel_barred passes the seat map's host family — see bite-proof
    nonpanel_barred = RD.receipt_disclosures.nonpanel_barred

    def bar(vendor, **cfg):
        state = _state(fixer=None, **cfg)
        return nonpanel_barred(state, state["config"])(vendor)

    assert bar("claude", host="anthropic", makers=["anthropic"]) is True
    assert bar("codex", host="anthropic", makers=["anthropic"]) is False
    # the host family, not the registry's anthropic, decides for the native seat
    assert bar("claude", host="openai", makers=["openai"]) is True
    assert bar("codex", host="openai", makers=["openai"]) is True
    assert bar("claude", host=None) is True
    state = _state(fixer=None)
    assert nonpanel_barred(state, None)("codex") is False


# --- review round 1 fixes: native stdout fallback, journal-only emission, rejection disclosure -----------

@pytest.mark.parametrize("phase,seat", FINDERS)
def test_native_vendor_on_the_stdout_fallback_contract_authenticates_from_the_manifest(phase, seat):
    # axis: a native (non-runner) vendor handed the stdout fallback contract is judged by the manifest
    # vendor like a file-channel host seat; a runner-channel vendor with no evidence still is not
    state = _state(fixer="codex", host="anthropic")
    art, why = _assemble_finder(state, phase, seat, None, "claude", wrapped=True)
    assert why is None and art["findings"] == [], (art, why)
    art, why = _assemble_finder(state, phase, seat, None, "cursor", wrapped=True)
    assert art is None and "executed=None:recorded=cursor" in why, (art, why)


def test_journal_only_emission_still_binds_the_fold_to_the_ordered_vendor(tmp_path):
    # axis: the emission is found through the journal when the state mirror is absent
    state = _state()
    _emit(state, tmp_path, RD.P_VERIFIERS, "codex")
    manifest_sha = state["_ordersAnchors"][RD._anchor_key(state["round"], RD.P_VERIFIERS, 0)]["manifestSha256"]
    RD._journal_append(str(tmp_path), {"cmd": "next", "outcome": "orders-emitted", "phase": RD.P_VERIFIERS,
                                       "round": state["round"], "attempt": 0,
                                       "manifestSha256": manifest_sha})
    state.pop("_ordersAnchors")
    assert RD._recorded_verifier_vendor(state, str(tmp_path)) == "codex"
    state["config"]["vendors"] = ["claude", "cursor"]  # the preference moved on after the emission
    row, unverified = _fold(state, tmp_path, _seat_artifact(state, "codex"))
    assert row["outcome"] == "verdicts-folded" and unverified == 0


def test_verifier_rejection_reaches_the_receipt(tmp_path):
    state = _state()
    _emit(state, tmp_path, RD.P_VERIFIERS, "codex")
    _fold(state, tmp_path, _seat_artifact(state, "cursor"))
    receipt = RD.build_receipt(state, session_dir=None, form=RD.RECEIPT_FORM_CERTIFIED)
    rows = receipt["rounds"][0]["verifierProvenance"]
    assert rows == [{"expected": "codex", "ran": "cursor", "outcome": "verdicts-ignored"}]
    assert any("verifier-verdicts-ignored" in line for line in receipt["degraded"]), receipt["degraded"]


def test_unauthenticated_library_finder_findings_are_retained_unverified():
    state, _calls = _library_run({"findings": [{"title": "real defect", "severity": "Important",
                                                "file": "a.py", "line": 1,
                                                "consequence": "a reviewer-found defect stays in the change"}],
                                  "vendor": "claude"})
    assert _parked(state)
    assert "expected=codex" in state["certification"]["reason"] and "reported=claude" in state["certification"]["reason"]
    kept = [f for f in state["findings"] if f.get("title") == "real defect"]
    assert len(kept) == 1 and kept[0]["unverified"] is True


# --- review round 2 fixes: authenticated duplicates stay ambiguous; a mixed manifest binds nothing ---------

def _mixed_emit(state, session_dir, phase):
    """An anchored, hash-valid manifest whose seats name codex and cursor (a preference edited mid-emission)."""
    manifest = _emit(state, session_dir, phase, "codex")
    path = RD._orders_manifest_path(str(session_dir), state["round"], phase, 0)
    manifest["seats"]["extra#0"] = {"vendor": "cursor", "channel": "stdout"}
    RR.atomic_write_json(path, manifest)
    state["_ordersAnchors"][RD._anchor_key(state["round"], phase, 0)] = {
        "manifestSha256": RR.sha256_text(RR.canonical(manifest))}


def test_mixed_manifest_verifier_verdicts_fold_as_silence(tmp_path):
    state = _state()
    _mixed_emit(state, tmp_path, RD.P_VERIFIERS)
    assert RD._emission_unverifiable(state, str(tmp_path), RD.P_VERIFIERS) == "emission-manifest-mixed-vendors"
    for ran in ("codex", "cursor"):  # neither the ordered nor the live vendor is authenticated
        state_i = _state()
        _mixed_emit(state_i, tmp_path, RD.P_VERIFIERS)
        row, unverified = _fold(state_i, tmp_path, _seat_artifact(state_i, ran))
        assert row == {"expected": "codex", "ran": None, "outcome": "verdicts-ignored",
                       "reason": "emission-manifest-mixed-vendors"}
        assert unverified == 1 and not state_i["rounds"]["1"]["verify"]["drops"]


@pytest.mark.parametrize("phase,seat", FINDERS)
def test_mixed_manifest_hand_finder_claim_is_refused(tmp_path, phase, seat):
    state = _state()
    _mixed_emit(state, tmp_path, phase)
    for vendor in ("codex", "cursor"):
        fault = RD._finder_hand_claim_fault(state, str(tmp_path), phase,
                                            {"findings": [], "reviewerVendor": vendor})
        assert fault is not None and "emission-manifest-mixed-vendors" in fault, fault


# --- per-seat verdict binding (WO-F3b): a verdict counts only from the seat its order assigned -----------
# `_emit_orders_manifest` records each verifier seat's assigned finding ids as `ids` (hashed into the
# emission anchor); `_assemble_verifiers` keeps a verdict only from the seat whose `ids` hold it.

def _binding_fixture():
    """A two-finding state, its two verifier seats and the two staged verdict ids (same order)."""
    state = _state()
    state["_toVerify"] = [{"file": "a.py", "line": 1, "title": "defect", "severity": "Important"},
                          {"file": "z.py", "line": 1, "title": "other", "severity": "Important"}]
    seats = RA.roster_for(RD.P_VERIFIERS, state, state["config"])[0]
    ids = [s["id"] for s in V.stage_ids(state["_toVerify"])]
    assert len(seats) == 2 and len(ids) == 2 and ids[0] != ids[1]
    return state, seats, ids


def _ids_manifest(seats, assigned, vendor="codex"):
    """An anchored-style orders manifest: seat i was ordered the ids in `assigned[i]` (None: no `ids` key)."""
    entries = {}
    for seat, ids in zip(seats, assigned):
        entries[RR.storage_key(seat, 0)] = {"vendor": vendor, "channel": "stdout"}
        if ids is not None:
            entries[RR.storage_key(seat, 0)]["ids"] = ids
    return {"seats": entries}


def _seat_env(seat, source, verdicts):
    env = P17._finder_envelope(seat, source=source)
    env["payload"] = {"verdicts": [{"id": vid, "verdict": verdict, "reason": "r", "evidence": "read x"}
                                   for vid, verdict in verdicts]}
    return env


def _assemble_seats(state, envs, manifest):
    art, why = RA.assemble(RD.P_VERIFIERS, envs, state, state["config"], orders_manifest=manifest)
    assert why is None, why
    return art


def _kept(art):
    return [(v["id"], v["verdict"]) for v in art["verdicts"]]


def test_authenticated_seats_repeating_an_id_are_bound_to_the_ordered_seat():
    # Rewritten from `test_authenticated_seats_repeating_an_id_keep_both_verdicts_for_the_ambiguity_rule`,
    # which asserted the deleted duplicate arbitration (both authenticated copies kept, the fold left to
    # call it ambiguous). Same input (two codex seats returning one id, disagreeing), now judged by the
    # binding: the seat the order assigned the id wins it, the other copy is dropped and disclosed, and
    # there is nothing left for the fold to call ambiguous; an id assigned to both is refused, not arbitrated.
    # axis: a repeated id is resolved by the ordered seat, never by "both authenticated, so both kept"
    state, seats, ids = _binding_fixture()
    vid = ids[0]
    envs = [_seat_env(seats[0], "codex", [(vid, "REFUTED")]), _seat_env(seats[1], "codex", [(vid, "CONFIRMED")])]
    art = _assemble_seats(state, envs, _ids_manifest(seats, [[vid], [ids[1]]]))
    assert _kept(art) == [(vid, "REFUTED")]
    assert art["provenance"]["unorderedVerdicts"] == [
        {"seat": seats[1], "id": vid, "orderedTo": RR.storage_key(seats[0], 0)}]
    applied = V.apply_verdicts(V.stage_ids(state["_toVerify"]), art["verdicts"])
    assert [d["id"] for d in applied["drops"]] == [vid] and applied["ambiguous"] == []
    # the same input against a manifest that assigned the id to both seats: refused, never arbitrated
    art = _assemble_seats(state, envs, _ids_manifest(seats, [[vid], [vid]]))
    assert art["verdicts"] == [] and art["provenance"]["doubleAssigned"] == [vid]
    applied = V.apply_verdicts(V.stage_ids(state["_toVerify"]), art["verdicts"])
    assert applied["ambiguous"] == [] and not applied["drops"] and len(applied["unverified"]) == 2


def test_b1_a_misrouted_eligible_seat_does_not_win_an_id_ordered_to_another_seat(tmp_path):
    # axis (B1): the verdict's seat must be the seat whose order assigned the id — an eligible vendor
    # (cursor) that was not the ordered one (the order named codex) wins nothing it was not assigned
    state, seats, ids = _binding_fixture()
    _emit(state, tmp_path, RD.P_VERIFIERS, "codex")
    envs = [_seat_env(seats[0], "codex", [(ids[0], "REFUTED")]),
            _seat_env(seats[1], "cursor", [(ids[0], "CONFIRMED"), (ids[1], "CONFIRMED")])]
    art = _assemble_seats(state, envs, _ids_manifest(seats, [[ids[0]], [ids[1]]]))
    assert _kept(art) == [(ids[0], "REFUTED"), (ids[1], "CONFIRMED")]
    assert art["verifierSeatVendors"] == {ids[0]: "codex", ids[1]: "cursor"}
    assert art["provenance"]["unorderedVerdicts"] == [
        {"seat": seats[1], "id": ids[0], "orderedTo": RR.storage_key(seats[0], 0)}]
    # through the fold: the ordered codex seat's verdict clears its finding; the cursor seat's own id is
    # ignored (cursor is not the vendor its order named)
    RD._fold_verifiers(state, state["config"], art, session_dir=str(tmp_path))
    verify = state["rounds"]["1"]["verify"]
    assert [d["id"] for d in verify["drops"]] == [ids[0]] and len(verify["unverified"]) == 1


def test_b2_a_same_vendor_repeat_from_an_unordered_seat_is_dropped_and_disclosed():
    # axis (B2): the repeat is judged by the seat that supplied it, not by its vendor — a second
    # codex seat (same vendor as the ordered one) repeating an id it was not assigned is dropped
    state, seats, ids = _binding_fixture()
    envs = [_seat_env(seats[0], "codex", [(ids[0], "REFUTED")]),
            _seat_env(seats[1], "codex", [(ids[0], "CONFIRMED"), (ids[1], "REFUTED")])]
    art = _assemble_seats(state, envs, _ids_manifest(seats, [[ids[0]], [ids[1]]]))
    assert _kept(art) == [(ids[0], "REFUTED"), (ids[1], "REFUTED")]
    assert art["provenance"]["unorderedVerdicts"] == [
        {"seat": seats[1], "id": ids[0], "orderedTo": RR.storage_key(seats[0], 0)}]
    applied = V.apply_verdicts(V.stage_ids(state["_toVerify"]), art["verdicts"])
    assert sorted(d["id"] for d in applied["drops"]) == sorted(ids) and applied["ambiguous"] == []


def test_b3_a_manifest_that_assigns_an_id_to_two_seats_keeps_no_verdict_for_it():
    # axis (B3, fail-closed edge E1): an id assigned to two seats is refused (not counted), never
    # arbitrated — neither the first seat nor either copy wins; the id stays unverified
    state, seats, ids = _binding_fixture()
    envs = [_seat_env(seats[0], "codex", [(ids[0], "REFUTED")]),
            _seat_env(seats[1], "codex", [(ids[0], "CONFIRMED")])]
    art = _assemble_seats(state, envs, _ids_manifest(seats, [[ids[0]], [ids[0]]]))
    assert art["verdicts"] == [] and art["verifierSeatVendors"] == {}
    assert art["provenance"]["doubleAssigned"] == [ids[0]]
    applied = V.apply_verdicts(V.stage_ids(state["_toVerify"]), art["verdicts"])
    assert not applied["drops"] and applied["ambiguous"] == [] and len(applied["unverified"]) == 2


def test_b4_copies_of_an_id_are_credited_only_to_its_ordered_seat_not_the_first_supplier():
    # axis (B4): the round-1 case (a seat copying another seat's id into its own output, supplied
    # first) — the id is credited by the seat the order assigned, never by who supplied it first
    state, seats, ids = _binding_fixture()
    envs = [_seat_env(seats[0], "codex", [(ids[0], "REFUTED"), (ids[1], "CONFIRMED")]),
            _seat_env(seats[1], "codex", [(ids[1], "REFUTED")])]
    art = _assemble_seats(state, envs, _ids_manifest(seats, [[ids[0]], [ids[1]]]))
    assert _kept(art) == [(ids[0], "REFUTED"), (ids[1], "REFUTED")]
    assert art["provenance"]["unorderedVerdicts"] == [
        {"seat": seats[0], "id": ids[1], "orderedTo": RR.storage_key(seats[1], 0)}]


@pytest.mark.parametrize("manifest", [
    pytest.param("no-ids-key", id="seat-entries-without-ids"),
    pytest.param("ids-not-a-list", id="ids-not-a-list"),
    pytest.param(None, id="no-manifest"),
    pytest.param({}, id="empty-manifest"),
])
def test_b5_a_manifest_that_assigns_no_ids_keeps_no_verdict(manifest):
    # axis (B5, fail-closed edge E2): no `ids` assigns nothing, so nothing is kept — never "whoever supplied it"
    state, seats, ids = _binding_fixture()
    if manifest == "no-ids-key":
        manifest = _ids_manifest(seats, [None, None])
    elif manifest == "ids-not-a-list":
        manifest = _ids_manifest(seats, [ids[0], ids[1]])
    envs = [_seat_env(seats[0], "codex", [(ids[0], "REFUTED")]), _seat_env(seats[1], "codex", [(ids[1], "REFUTED")])]
    art = _assemble_seats(state, envs, manifest)
    assert art["verdicts"] == [] and art["verifierSeatVendors"] == {}
    assert [(u["id"], u["orderedTo"]) for u in art["provenance"]["unorderedVerdicts"]] == [
        (ids[0], None), (ids[1], None)]
    assert "doubleAssigned" not in art["provenance"]
    applied = V.apply_verdicts(V.stage_ids(state["_toVerify"]), art["verdicts"])
    assert not applied["drops"] and len(applied["unverified"]) == 2


def test_b6_the_emitted_verifier_manifest_records_each_seats_assigned_ids(tmp_path):
    # axis (B6): the emission records `ids` per verifier seat — the binding reads them from the anchored manifest
    session_dir, gitdir, head_path = IT._bootstrap(tmp_path, name="emit-records-ids")
    IT._drive_to_phase(session_dir, gitdir, [IT._blocking_finding("unchecked index", 2)], head_path,
                       RD.P_VERIFIERS)
    state = IT._state(session_dir)
    pend = state["pending"]
    manifest = RD._anchored_orders_manifest(state, session_dir, pend["round"], pend["phase"], pend["attempt"])
    assert manifest, "the verifier emission must verify against its anchor"
    slots = IT._slots_of(RA.roster_for(RD.P_VERIFIERS, state, state["config"])[0])
    assert slots
    for seat, occurrence in slots:
        assigned = [f["id"] for f in IT._cluster_for(pend, seat).get("findings") or []]
        assert assigned and manifest["seats"][RR.storage_key(seat, occurrence)].get("ids") == assigned
