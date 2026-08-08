"""Tests for `round_adapters` — the per-phase aggregate adapters (#723).

The load-bearing test in this file is the FIXTURE-EQUIVALENCE test, one per phase: build the seat
envelopes, assemble, drive the REAL driver through that phase with the assembled artifact, and
assert the resulting driver state is identical to driving it with the hand-written artifact that
already appears in `test_round_driver.py`. Asserting dict keys would prove nothing — the claim is
that the fold cannot tell the two apart, and only running the fold shows that.

The rest pin the fail-closed edges (each names its exact reason string), the three
`missing_policy` values, and the trust rule: a manifest comes ONLY from the orchestrator's
out-of-band dispatch record, never from a seat's own vendor echo.
"""
import os

import pytest

import audits
import round_adapters as RA
import round_driver as RD
import round_records as RR
import verification

# --- diffs (same shapes test_round_driver.py drives with) ---------------------

DIFF = ("diff --git a/f.py b/f.py\nindex 1..2 100644\n--- a/f.py\n+++ b/f.py\n"
        "@@ -1 +1,2 @@\n-old\n+new\n+more\n")
HEAD = ("diff --git a/f.py b/f.py\nindex 2..3 100644\n--- a/f.py\n+++ b/f.py\n"
        "@@ -1 +1,3 @@\n-old\n+new\n+more\n+fixed\n")
NEW_SURFACE = ("diff --git a/newsurf.py b/newsurf.py\nindex 0..1 100644\n--- a/newsurf.py\n"
               "+++ b/newsurf.py\n@@ -0,0 +1,2 @@\n+ns\n+ns2\n")
HEAD_NEW_SURFACE = HEAD + NEW_SURFACE


def _big_diff(n_files=25):
    return "".join(
        "diff --git a/f%d.py b/f%d.py\nindex 1..2 100644\n--- a/f%d.py\n+++ b/f%d.py\n"
        "@@ -1 +1 @@\n-a\n+b\n" % (i, i, i, i) for i in range(n_files))


_A_FINDING = [{"title": "bug", "severity": "Important", "file": "f.py", "line": 1}]
_TWO_FINDINGS = [{"title": "bug", "severity": "Important", "file": "f.py", "line": 1},
                 {"title": "other bug", "severity": "Minor", "file": "f.py", "line": 2}]


def _cfg(**over):
    base = {"leg": "code", "vendors": ["claude", "codex"], "diff": DIFF, "fixerVendor": "claude"}
    base.update(over)
    return base


def _responder(round1_findings=None, head=HEAD, grouping=None, verify="pass"):
    """The hand-written artifact per phase — the shapes `test_round_driver.py::_responder` uses."""
    def respond(phase, payload, rnd):
        if phase == RD.P_PANEL:
            seats = {d: {"findings": []} for d in RD.DIMENSIONS}
            if rnd == 1 and round1_findings:
                seats["code-reviewer"] = {"findings": list(round1_findings)}
            return {"seats": seats}
        if phase == RD.P_VERIFIERS:
            return {"verdicts": [{"id": i, "verdict": "CONFIRMED", "evidence": "ran"}
                                 for c in payload.get("clusters", []) for i in c.get("ids", [])]}
        if phase == RD.P_SYNTHESIS:
            return {"grouping": grouping}
        if phase == RD.P_GAPSWEEP:
            return {"findings": []}
        if phase == RD.P_AUDITS:
            return {"results": [{"id": t["id"], "ruling": "discharged", "reason": "r",
                                 "evidence": "e", "auditorVendor": t.get("auditorVendor")}
                                for t in payload.get("targets", [])],
                    "collectionManifest": {t["id"]: t.get("auditorVendor")
                                           for t in payload.get("targets", [])}}
        if phase == RD.P_SCOPED:
            return {"findings": []}
        if phase == RD.P_FIXER:
            return {"fixes": [], "headDiff": head}
        if phase == RD.P_VERIFY:
            return {"result": verify}
        return {}
    return respond


def _drive_to_phase(session_dir, cfg, respond, target_phase, max_steps=80):
    """Drive next/submit until the PENDING step is `target_phase`; return that `next`."""
    first = True
    for _ in range(max_steps):
        n = RD.cmd_next(session_dir, cfg if first else None)
        first = False
        assert n["ok"], n
        if n.get("phase") == target_phase:
            return n
        assert n["action"] != RD.P_TERMINAL, "reached terminal before %s" % target_phase
        s = RD.cmd_submit(session_dir, n["phase"], n["attempt"], n["expectedStateHash"],
                          respond(n["phase"], n["payload"], n["round"]))
        assert s["ok"], s
    raise AssertionError("never reached %s within %d steps" % (target_phase, max_steps))


def _drive_on(session_dir, respond, max_steps=80):
    """Keep driving an already-started session to its terminal; return the terminal payload."""
    for _ in range(max_steps):
        n = RD.cmd_next(session_dir)
        assert n["ok"], n
        if n["action"] == RD.P_TERMINAL:
            return n["payload"]
        s = RD.cmd_submit(session_dir, n["phase"], n["attempt"], n["expectedStateHash"],
                          respond(n["phase"], n["payload"], n["round"]))
        assert s["ok"], s
    raise AssertionError("no terminal within %d steps" % max_steps)


# --- envelopes ----------------------------------------------------------------

def _result_env(seat, payload, vendor="claude", model="opus-5", occurrence=None):
    env = {"schema": RR.SEAT_RESULT_SCHEMA, "seat": seat, "attempt": 0, "vendor": vendor,
           "model": model, "payload": payload}
    if occurrence is not None:
        env["occurrence"] = occurrence
    return env


def _missing_env(seat, reason=None, vendor="claude", occurrence=None):
    env = {"schema": RR.SEAT_MISSING_SCHEMA, "seat": seat, "attempt": 0, "vendor": vendor,
           "model": "opus-5", "reason": reason or RR.MISSING_REASONS[0]}
    if occurrence is not None:
        env["occurrence"] = occurrence
    return env


def _at(tmp_path, phase, cfg=None, respond=None, name="s"):
    """A fresh session driven to `phase`; returns (session_dir, next, pre-fold state)."""
    d = str(tmp_path / name)
    os.makedirs(d)
    n = _drive_to_phase(d, cfg or _cfg(), respond or _responder(round1_findings=_A_FINDING), phase)
    ok, state = RD.load_state(d)
    assert ok and state is not None
    return d, n, state


def _state_without_receipt_keys(state):
    """Driver state minus keys that legitimately differ between two artifacts or sessions.

    `lastAccepted` carries the submitted artifact hash; `_ordersAnchors` carries a
    session-id-bound manifest sha256 that differs per session dir even when the fold is
    otherwise identical."""
    out = dict(state)
    out.pop("lastAccepted", None)
    anchors = out.get("_ordersAnchors")
    if isinstance(anchors, dict):
        stripped = {}
        for key, anchor in anchors.items():
            if isinstance(anchor, dict):
                copy = dict(anchor)
                copy.pop("manifestSha256", None)
                copy.pop("path", None)
                stripped[key] = copy
            else:
                stripped[key] = anchor
        out["_ordersAnchors"] = stripped
    return out


def _assert_fold_equivalent(tmp_path, phase, build, cfg=None, respond_factory=None):
    """The point of this module, per phase.

    Drive TWO fresh sessions to `phase`. Submit the hand-written artifact to one and the ASSEMBLED
    artifact to the other; assert both are accepted by the real submit path and that the resulting
    driver states are identical. `build(next, state) -> (hand_artifact, envelopes, assemble_kwargs)`.
    """
    cfg = cfg or _cfg()
    respond_factory = respond_factory or (
        lambda: _responder(round1_findings=_A_FINDING))
    d_hand, n_hand, _state_hand = _at(tmp_path, phase, dict(cfg), respond_factory(), name="hand")
    d_asm, n_asm, state_asm = _at(tmp_path, phase, dict(cfg), respond_factory(), name="assembled")
    for key in ("phase", "round", "attempt", "action"):
        assert n_hand[key] == n_asm[key], (
            "the two sessions diverged before the phase under test (%s)" % key)

    hand_artifact, envelopes, kwargs = build(n_asm, state_asm)
    artifact, reason = RA.assemble(phase, envelopes, state_asm, state_asm["config"], **kwargs)
    assert reason is None, reason
    assert artifact is not None

    out_hand = RD.cmd_submit(d_hand, n_hand["phase"], n_hand["attempt"],
                             n_hand["expectedStateHash"], hand_artifact)
    assert out_hand["ok"] is True, out_hand
    out_asm = RD.cmd_submit(d_asm, n_asm["phase"], n_asm["attempt"],
                            n_asm["expectedStateHash"], artifact)
    assert out_asm["ok"] is True, out_asm

    ok_h, after_hand = RD.load_state(d_hand)
    ok_a, after_asm = RD.load_state(d_asm)
    assert ok_h and ok_a
    assert _state_without_receipt_keys(after_asm) == _state_without_receipt_keys(after_hand)
    return artifact, hand_artifact


# =============================================================================
# fixture equivalence — one per phase
# =============================================================================

def test_panel_assembles_to_the_hand_written_artifact(tmp_path):
    def build(n, state):
        hand = {"seats": {d: {"findings": []} for d in RD.DIMENSIONS}}
        hand["seats"]["code-reviewer"] = {"findings": list(_A_FINDING)}
        # Same provenance the assembled path records when no dispatch manifest or canary is supplied.
        hand["provenance"] = {"dispatchManifestUnavailable": True, "canaryUnavailable": True}
        envelopes = [_result_env(d, dict(hand["seats"][d])) for d in RD.DIMENSIONS]
        return hand, envelopes, {}

    artifact, hand = _assert_fold_equivalent(tmp_path, RD.P_PANEL, build)
    assert artifact["seats"] == hand["seats"]
    # No dispatch manifest and no canary were supplied, so neither key is invented — the driver's
    # own provenance-unavailable / canaryUnverified disclosures stay the ones that fire.
    assert "ranManifest" not in artifact and "canaryResult" not in artifact
    expected_prov = {"byPhase": {RD.P_PANEL: {"dispatchManifestUnavailable": True,
                                               "canaryUnavailable": True}}}
    # `_fold_panel` pops `provenance` from the submitted artifact; both paths record it durably.
    ok_h, st_h = RD.load_state(str(tmp_path / "hand"))
    ok_a, st_a = RD.load_state(str(tmp_path / "assembled"))
    assert ok_h and ok_a
    assert st_h["rounds"]["1"]["adapterProvenance"] == expected_prov
    assert st_a["rounds"]["1"]["adapterProvenance"] == expected_prov


def test_panel_confidence_and_tier_ride_into_the_review_record(tmp_path):
    """`_fold_panel` reads `confidence`/`tier` off each seat into the per-dimension record
    `_confirmation_qualifies` judges — so the adapter must carry both, not just findings."""
    d, n, state = _at(tmp_path, RD.P_PANEL)
    seats = {dim: {"findings": [], "confidence": "medium", "tier": RD.CHEAP}
             for dim in RD.DIMENSIONS}
    envelopes = [_result_env(dim, dict(seats[dim])) for dim in RD.DIMENSIONS]
    artifact, reason = RA.assemble(RD.P_PANEL, envelopes, state, state["config"])
    assert reason is None
    assert RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"], artifact)["ok"]
    ok, after = RD.load_state(d)
    record = after["_records"][-1]
    for dim in RD.DIMENSIONS:
        assert record["dimensions"][dim]["confidence"] == "medium", record
        assert record["dimensions"][dim]["tier"] == RD.CHEAP, record


def test_panel_with_manifest_and_canary_matches_the_hand_written_envelope(tmp_path):
    """The richer panel artifact: a trusted ranManifest + a per-vendor canary list. Equivalence is
    against the hand-written four-key envelope `_fold_panel` already consumes."""
    seat_map = {"seats": {d: {"vendor": "codex"} for d in RD.DIMENSIONS}}
    probes = [{"engine": "codex", "engaged": True, "evidence": {"probe": "seat_canary"}}]

    def build(n, state):
        seats = {d: {"findings": []} for d in RD.DIMENSIONS}
        seats["code-reviewer"] = {"findings": list(_A_FINDING)}
        hand = {"seats": seats, "seatMap": seat_map,
                "ranManifest": {d: "codex" for d in RD.DIMENSIONS},
                "canaryResult": probes}
        envelopes = [_result_env(d, dict(seats[d]), vendor="codex") for d in RD.DIMENSIONS]
        manifest = {d: {"vendor": "codex", "model": "gpt-5", "engine": "codex"}
                    for d in RD.DIMENSIONS}
        state["seatMap"] = dict(seat_map)
        return hand, envelopes, {"dispatch_manifest": manifest, "canary": probes}

    # Both sessions must carry the same seat map, so it is seeded into state before assembly and
    # rides the hand-written artifact too (the fold merges `artifact["seatMap"]` into state).
    artifact, hand = _assert_fold_equivalent(tmp_path, RD.P_PANEL, build)
    assert artifact["ranManifest"] == hand["ranManifest"]
    assert artifact["canaryResult"] == probes
    assert artifact["seatMap"] == seat_map


def test_verifiers_assembles_verdicts_in_cluster_order(tmp_path):
    def build(n, state):
        clusters = n["payload"]["clusters"]
        assert clusters
        hand = {"verdicts": [{"id": i, "verdict": "CONFIRMED", "evidence": "ran"}
                             for c in clusters for i in c["ids"]]}
        envelopes = [
            _result_env(RA.VERIFIER_SEAT_PREFIX + c["key"],
                        {"verdicts": [{"id": i, "verdict": "CONFIRMED", "evidence": "ran"}
                                      for i in c["ids"]]})
            for c in clusters]
        return hand, envelopes, {}

    artifact, hand = _assert_fold_equivalent(tmp_path, RD.P_VERIFIERS, build)
    assert artifact["verdicts"] == hand["verdicts"]


def test_synthesis_passes_the_grouping_through(tmp_path):
    grouping = [{"group_id": "g1", "member_ids": ["v0", "v1"]}]

    def build(n, state):
        hand = {"grouping": grouping}
        return hand, [_result_env(RA.SEAT_SYNTHESIS, {"grouping": grouping})], {}

    artifact, hand = _assert_fold_equivalent(
        tmp_path, RD.P_SYNTHESIS, build,
        respond_factory=lambda: _responder(round1_findings=_TWO_FINDINGS, grouping=grouping))
    assert artifact["grouping"] == grouping


def test_gap_sweep_assembles_its_candidate_findings(tmp_path):
    big = _big_diff()

    def build(n, state):
        hand = {"findings": []}
        return hand, [_result_env(RA.SEAT_GAPSWEEP, {"findings": []})], {}

    artifact, _hand = _assert_fold_equivalent(
        tmp_path, RD.P_GAPSWEEP, build, cfg=_cfg(diff=big),
        respond_factory=lambda: _responder(round1_findings=_A_FINDING))
    assert artifact == {"findings": []}


def test_fixer_passes_its_payload_through(tmp_path):
    def build(n, state):
        hand = {"fixes": [], "headDiff": HEAD}
        return hand, [_result_env(RA.SEAT_FIXER, {"fixes": [], "headDiff": HEAD})], {}

    artifact, hand = _assert_fold_equivalent(tmp_path, RD.P_FIXER, build)
    assert artifact == hand


def test_verify_assembles_the_result_token(tmp_path):
    def build(n, state):
        hand = {"result": "pass"}
        payload = {"result": "pass", "command": "pytest -q", "exit": 0, "outputSha256": "ab" * 32}
        return hand, [_result_env(RA.SEAT_VERIFY, payload)], {}

    artifact, _hand = _assert_fold_equivalent(tmp_path, RD.P_VERIFY, build)
    assert artifact["result"] == "pass"
    # The extras the fold tolerates ride along; only `result` is consumed.
    assert artifact["command"] == "pytest -q" and artifact["exit"] == 0


def test_audits_assembles_results_and_a_trusted_collection_manifest(tmp_path):
    def build(n, state):
        targets = n["payload"]["targets"]
        assert targets
        results = [{"id": t["id"], "ruling": "discharged", "reason": "r", "evidence": "e",
                    "auditorVendor": t.get("auditorVendor")} for t in targets]
        hand = {"results": results,
                "collectionManifest": {t["id"]: t.get("auditorVendor") for t in targets}}
        envelopes = [_result_env(t["id"], dict(r), vendor=t.get("auditorVendor"))
                     for t, r in zip(targets, results)]
        manifest = {t["id"]: {"vendor": t.get("auditorVendor"), "model": "m", "engine": "e"}
                    for t in targets}
        return hand, envelopes, {"dispatch_manifest": manifest}

    artifact, hand = _assert_fold_equivalent(
        tmp_path, RD.P_AUDITS, build,
        respond_factory=lambda: _responder(round1_findings=_A_FINDING, head=HEAD_NEW_SURFACE))
    assert artifact["results"] == hand["results"]
    assert artifact["collectionManifest"] == hand["collectionManifest"]


def test_scoped_finder_assembles_its_candidate_findings(tmp_path):
    candidates = [{"title": "new bug", "severity": "Important", "file": "newsurf.py", "line": 1}]

    def build(n, state):
        hand = {"findings": list(candidates)}
        return hand, [_result_env(RA.SEAT_SCOPED, {"findings": list(candidates)})], {}

    artifact, hand = _assert_fold_equivalent(
        tmp_path, RD.P_SCOPED, build,
        respond_factory=lambda: _responder(round1_findings=_A_FINDING, head=HEAD_NEW_SURFACE))
    assert artifact == hand


# =============================================================================
# roster
# =============================================================================

def test_roster_panel_is_the_configured_dimensions(tmp_path):
    _d, _n, state = _at(tmp_path, RD.P_PANEL)
    keys, reason = RA.roster_for(RD.P_PANEL, state, state["config"])
    assert reason is None
    assert keys == RD.DIMENSIONS


def test_roster_verifiers_is_one_seat_per_cluster(tmp_path):
    _d, n, state = _at(tmp_path, RD.P_VERIFIERS)
    keys, reason = RA.roster_for(RD.P_VERIFIERS, state, state["config"])
    assert reason is None
    assert keys == [RA.VERIFIER_SEAT_PREFIX + c["key"] for c in n["payload"]["clusters"]]


def test_roster_audits_is_the_audit_target_ids(tmp_path):
    _d, n, state = _at(tmp_path, RD.P_AUDITS,
                       respond=_responder(round1_findings=_A_FINDING, head=HEAD_NEW_SURFACE))
    keys, reason = RA.roster_for(RD.P_AUDITS, state, state["config"])
    assert reason is None
    assert keys == [t["id"] for t in n["payload"]["targets"]]


def test_roster_audits_keeps_two_targets_that_share_one_id(tmp_path):
    """Audit target ids are LINE-LESS (`finding_identity` is `file::normalized-title`), so two
    distinct targets can carry one id. The roster keeps both slots — collapsing them would silently
    drop a target's audit."""
    shared = "f.py::unchecked return value"
    state = {"_auditTargets": [{"id": shared, "line": 1}, {"id": shared, "line": 90}]}
    keys, reason = RA.roster_for(RD.P_AUDITS, state, {})
    assert reason is None and keys == [shared, shared]
    payload = {"id": shared, "ruling": audits.AUDIT_RULINGS[0], "reason": "r"}
    envelopes = [_result_env(shared, dict(payload), occurrence=0),
                 _result_env(shared, dict(payload), occurrence=1)]
    artifact, reason = RA.assemble(RD.P_AUDITS, envelopes, state, {})
    assert reason is None
    assert len(artifact["results"]) == 2


@pytest.mark.parametrize("phase,seat", [
    (RD.P_SYNTHESIS, RA.SEAT_SYNTHESIS),
    (RD.P_GAPSWEEP, RA.SEAT_GAPSWEEP),
    (RD.P_SCOPED, RA.SEAT_SCOPED),
    (RD.P_VERIFY, RA.SEAT_VERIFY),
    (RD.P_FIXER, RA.SEAT_FIXER),
])
def test_roster_single_seat_phases(phase, seat):
    assert RA.roster_for(phase, {}, {}) == ([seat], None)


def test_roster_unknown_phase_names_it():
    keys, reason = RA.roster_for("no-such-phase", {}, {})
    assert keys == [] and reason == "unknown-phase:no-such-phase"


# =============================================================================
# missing_policy — the safety surface
# =============================================================================

def test_missing_policy_per_phase():
    assert RA.missing_policy(RD.P_PANEL) == RA.MISSING_SEAT_STATUS
    assert RA.missing_policy(RD.P_VERIFIERS) == RA.MISSING_FOLD_FAIL_CLOSED
    assert RA.missing_policy(RD.P_AUDITS) == RA.MISSING_FOLD_FAIL_CLOSED
    for phase in (RD.P_SYNTHESIS, RD.P_GAPSWEEP, RD.P_SCOPED, RD.P_VERIFY, RD.P_FIXER):
        assert RA.missing_policy(phase) == RA.MISSING_REFUSE_FOLD


def test_missing_policy_unknown_phase_is_the_conservative_value():
    """A caller branching on the value must not fall open on a phase this module does not model."""
    assert RA.missing_policy("no-such-phase") == RA.MISSING_REFUSE_FOLD


def test_seat_status_policy_a_missing_panel_seat_folds_missing_and_withholds_full_panel(tmp_path):
    """`seat-status`: the missing dimension lands on the fold's OWN missing path — `missingSeats`,
    a `panel-seat-missing` decision, `fullPanelRan` False. It never becomes a clean `run`."""
    d, n, state = _at(tmp_path, RD.P_PANEL)
    envelopes = [_result_env(dim, {"findings": []}) for dim in RD.DIMENSIONS
                 if dim != "security-reviewer"]
    envelopes.append(_missing_env("security-reviewer", reason=RR.MISSING_REASONS[1]))
    artifact, reason = RA.assemble(RD.P_PANEL, envelopes, state, state["config"])
    assert reason is None
    assert "security-reviewer" not in artifact["seats"]
    assert artifact["provenance"]["missingSeats"] == [
        {"seat": "security-reviewer", "occurrence": 0, "reason": RR.MISSING_REASONS[1]}]
    assert RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"], artifact)["ok"]
    ok, after = RD.load_state(d)
    assert after["rounds"]["1"]["seatStatus"]["security-reviewer"] == "missing"
    assert after["rounds"]["1"]["missingSeats"] == ["security-reviewer"]
    assert after["fullPanelRan"] is False
    assert any(dec["kind"] == "panel-seat-missing" for dec in after["decisions"])


def test_seat_status_policy_covers_a_roster_seat_that_landed_nothing_at_all(tmp_path):
    """No envelope is the same coverage gap as a recorded `seat-missing/1` — never a clean run."""
    _d, _n, state = _at(tmp_path, RD.P_PANEL)
    envelopes = [_result_env(dim, {"findings": []}) for dim in RD.DIMENSIONS
                 if dim != "test-reviewer"]
    artifact, reason = RA.assemble(RD.P_PANEL, envelopes, state, state["config"])
    assert reason is None
    assert "test-reviewer" not in artifact["seats"]
    assert artifact["provenance"]["missingSeats"] == [
        {"seat": "test-reviewer", "occurrence": 0, "reason": RA.NO_ENVELOPE}]


def test_fold_fail_closed_policy_a_silent_verifier_cluster_is_omitted_not_emptied(tmp_path):
    """`fold-fail-closed`: the cluster's findings stay UNVERIFIED (apply_verdicts keeps them
    PLAUSIBLE). An empty verdict list would read as 'verified, nothing found'."""
    d, n, state = _at(tmp_path, RD.P_VERIFIERS)
    clusters = n["payload"]["clusters"]
    assert clusters
    envelopes = [_missing_env(RA.VERIFIER_SEAT_PREFIX + c["key"]) for c in clusters]
    artifact, reason = RA.assemble(RD.P_VERIFIERS, envelopes, state, state["config"])
    assert reason is None
    assert artifact["verdicts"] == []
    assert [m["seat"] for m in artifact["provenance"]["unverifiedClusters"]] == [
        RA.VERIFIER_SEAT_PREFIX + c["key"] for c in clusters]
    assert RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"], artifact)["ok"]
    ok, after = RD.load_state(d)
    # Silence is DISCLOSED as unverified and the findings survive — nothing was certified verified.
    assert after["rounds"]["1"]["verify"]["unverified"], after["rounds"]["1"]["verify"]
    assert after["rounds"]["1"]["verify"]["drops"] == []
    assert after["_verified"], "a silent verifier must not drop the findings"
    assert after["rounds"]["1"]["adapterProvenance"]["byPhase"][RD.P_VERIFIERS]["unverifiedClusters"]


def test_fold_fail_closed_policy_a_silent_auditor_leaves_its_target_not_discharged(tmp_path):
    d, n, state = _at(tmp_path, RD.P_AUDITS,
                      respond=_responder(round1_findings=_A_FINDING, head=HEAD_NEW_SURFACE))
    targets = n["payload"]["targets"]
    envelopes = [_missing_env(t["id"]) for t in targets]
    manifest = {t["id"]: {"vendor": t.get("auditorVendor")} for t in targets}
    artifact, reason = RA.assemble(RD.P_AUDITS, envelopes, state, state["config"],
                                   dispatch_manifest=manifest)
    assert reason is None
    assert artifact["results"] == []
    assert [m["seat"] for m in artifact["provenance"]["unauditedTargets"]] == [
        t["id"] for t in targets]
    assert RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"], artifact)["ok"]
    ok, after = RD.load_state(d)
    outcomes = after["auditRounds"][-1]["outcomes"]
    assert outcomes and all(o["ruling"] == audits.AUDIT_RULINGS[1] for o in outcomes), outcomes
    assert any(dec["kind"] == "not-discharged" for dec in after["decisions"])


@pytest.mark.parametrize("phase,seat,payload", [
    (RD.P_SYNTHESIS, RA.SEAT_SYNTHESIS, {"grouping": None}),
    (RD.P_GAPSWEEP, RA.SEAT_GAPSWEEP, {"findings": []}),
    (RD.P_SCOPED, RA.SEAT_SCOPED, {"findings": []}),
    (RD.P_VERIFY, RA.SEAT_VERIFY, {"result": "pass"}),
    (RD.P_FIXER, RA.SEAT_FIXER, {"fixes": []}),
])
def test_refuse_fold_policy_every_single_seat_phase_refuses_a_missing_seat(phase, seat, payload):
    """`refuse-fold`: an empty success artifact at a single-seat phase could let the run certify.
    The adapter refuses so the caller re-dispatches or parks — it never synthesizes the artifact."""
    for envelopes in ([], [_missing_env(seat)]):
        artifact, reason = RA.assemble(phase, envelopes, {}, {})
        assert artifact is None, ("a missing %s must never assemble a success artifact, got %r"
                                  % (seat, artifact))
        assert reason == "missing-seat-refuse-fold:%s" % seat
    # the same phase with a landed seat still assembles
    artifact, reason = RA.assemble(phase, [_result_env(seat, payload)], {}, {})
    assert reason is None and artifact is not None


def test_missing_scoped_finder_refuses_where_an_empty_artifact_would_certify(tmp_path):
    """The exact defect `refuse-fold` prevents, shown against its counterfactual.

    Half A: a missing scoped-finder seat assembles NOTHING.
    Half B: the artifact the refusal withholds — `{"findings": []}` — settles the delta and drives
    the run to a CERTIFYING terminal. Without half B the refusal could be cost-free; with it, the
    refusal is the only thing standing between silence and a certification.
    """
    respond = _responder(round1_findings=_A_FINDING, head=HEAD_NEW_SURFACE)
    d, n, state = _at(tmp_path, RD.P_SCOPED, respond=respond, name="refused")
    artifact, reason = RA.assemble(RD.P_SCOPED, [_missing_env(RA.SEAT_SCOPED)], state,
                                   state["config"])
    assert artifact is None, "a missing scoped-finder must never assemble a success artifact"
    assert reason == "missing-seat-refuse-fold:%s" % RA.SEAT_SCOPED

    d2, n2, _state2 = _at(tmp_path, RD.P_SCOPED, respond=_responder(
        round1_findings=_A_FINDING, head=HEAD_NEW_SURFACE), name="counterfactual")
    assert RD.cmd_submit(d2, n2["phase"], n2["attempt"], n2["expectedStateHash"],
                         {"findings": []})["ok"]
    payload = _drive_on(d2, _responder(round1_findings=_A_FINDING, head=HEAD_NEW_SURFACE))
    assert payload["verdict"] == "converged", payload
    assert payload["certification"]["shape"] is not None, payload


# =============================================================================
# fail-closed edges — each names its exact reason
# =============================================================================

def test_edge_unknown_phase():
    artifact, reason = RA.assemble("no-such-phase", [], {}, {})
    assert artifact is None and reason == "unknown-phase:no-such-phase"


def test_edge_envelopes_not_a_list():
    artifact, reason = RA.assemble(RD.P_SCOPED, {"seat": RA.SEAT_SCOPED}, {}, {})
    assert artifact is None and reason == "envelopes-not-a-list:dict"


def test_edge_envelope_list_containing_a_non_dict():
    envelopes = [_result_env(RA.SEAT_SCOPED, {"findings": []}), "not-an-envelope"]
    artifact, reason = RA.assemble(RD.P_SCOPED, envelopes, {}, {})
    assert artifact is None and reason == "envelope-not-an-object:index-1:str"


def test_edge_two_envelopes_for_the_same_seat_refuse_never_last_wins():
    envelopes = [_result_env(RA.SEAT_SCOPED, {"findings": []}),
                 _result_env(RA.SEAT_SCOPED, {"findings": [{"title": "second"}]})]
    artifact, reason = RA.assemble(RD.P_SCOPED, envelopes, {}, {})
    assert artifact is None, "an ambiguous seat must never resolve last-wins"
    assert reason == "duplicate-envelope:%s#0" % RA.SEAT_SCOPED


def test_edge_seat_not_in_the_roster():
    envelopes = [_result_env(RA.SEAT_SCOPED, {"findings": []}),
                 _result_env("stowaway", {"findings": []})]
    artifact, reason = RA.assemble(RD.P_SCOPED, envelopes, {}, {})
    assert artifact is None and reason == "seat-not-in-roster:stowaway"


def test_edge_occurrence_beyond_the_roster():
    shared = "f.py::t"
    state = {"_auditTargets": [{"id": shared}]}
    envelopes = [_result_env(shared, {"id": shared, "ruling": audits.AUDIT_RULINGS[0],
                                      "reason": "r"}, occurrence=1)]
    artifact, reason = RA.assemble(RD.P_AUDITS, envelopes, state, {})
    assert artifact is None and reason == "seat-occurrence-not-in-roster:%s#1" % shared


def test_edge_seat_result_envelope_with_no_payload_key():
    envelope = {"schema": RR.SEAT_RESULT_SCHEMA, "seat": RA.SEAT_SCOPED, "attempt": 0,
                "vendor": "claude", "model": "opus-5"}
    artifact, reason = RA.assemble(RD.P_SCOPED, [envelope], {}, {})
    assert artifact is None and reason == "seat-result-missing-payload:%s" % RA.SEAT_SCOPED


def test_edge_unknown_envelope_schema():
    envelope = {"schema": "seat-result/999", "seat": RA.SEAT_SCOPED, "payload": {"findings": []}}
    artifact, reason = RA.assemble(RD.P_SCOPED, [envelope], {}, {})
    assert artifact is None and reason == "unknown-envelope-schema:%s:seat-result/999" % RA.SEAT_SCOPED


def test_edge_payload_fault_refuses_the_whole_assemble_naming_seat_and_field():
    envelopes = [_result_env(RA.SEAT_SCOPED, {"findings": "not-a-list"})]
    artifact, reason = RA.assemble(RD.P_SCOPED, envelopes, {}, {})
    assert artifact is None
    assert reason == "payload-fault:%s:`findings` is str, not a list" % RA.SEAT_SCOPED


def test_edge_dispatch_manifest_present_but_not_a_dict(tmp_path):
    _d, _n, state = _at(tmp_path, RD.P_PANEL)
    envelopes = [_result_env(dim, {"findings": []}) for dim in RD.DIMENSIONS]
    artifact, reason = RA.assemble(RD.P_PANEL, envelopes, state, state["config"],
                                   dispatch_manifest=[{"vendor": "codex"}])
    assert artifact is None and reason == "dispatch-manifest-not-a-dict:list"


def test_edge_canary_entry_with_no_engine(tmp_path):
    """A probe with no `engine` matches NO vendor in `canary_liveness` — it is silently inert while
    reading as 'a control probe was supplied'."""
    _d, _n, state = _at(tmp_path, RD.P_PANEL)
    envelopes = [_result_env(dim, {"findings": []}) for dim in RD.DIMENSIONS]
    artifact, reason = RA.assemble(RD.P_PANEL, envelopes, state, state["config"],
                                   canary=[{"engine": "codex", "engaged": True},
                                           {"engaged": True}])
    assert artifact is None and reason == "canary-entry-has-no-engine:index-1"


def test_edge_envelope_with_no_seat():
    artifact, reason = RA.assemble(RD.P_SCOPED, [{"schema": RR.SEAT_RESULT_SCHEMA,
                                                  "payload": {"findings": []}}], {}, {})
    assert artifact is None and reason == "envelope-has-no-seat:index-0"


def test_assemble_never_raises_on_hostile_input():
    for bad in (None, 3, "x", [None], [{"seat": RA.SEAT_SCOPED, "schema": None}]):
        artifact, reason = RA.assemble(RD.P_SCOPED, bad, None, None)
        assert artifact is None and isinstance(reason, str) and reason


# =============================================================================
# payload_fault
# =============================================================================

def test_payload_fault_unknown_phase_and_non_dict_payload():
    assert RA.payload_fault("nope", {}, "s") == "unknown-phase:nope"
    assert RA.payload_fault(RD.P_SCOPED, ["findings"], "s") == "payload is list, not an object"


@pytest.mark.parametrize("payload,fragment", [
    ({}, "`findings` is missing"),
    ({"findings": {}}, "`findings` is dict, not a list"),
    ({"findings": ["x"]}, "`findings`[0] is str, not an object"),
    ({"findings": [], "confidence": 3}, "`confidence` is int, not a non-empty string"),
    ({"findings": [], "tier": ""}, "`tier` is str, not a non-empty string"),
    ({"findings": [], "receiptMissing": "yes"}, "`receiptMissing` is str, not a boolean"),
    ({"findings": [], "reason": 7}, "`reason` is int, not a string"),
])
def test_panel_payload_faults(payload, fragment):
    fault = RA.payload_fault(RD.P_PANEL, payload, "code-reviewer")
    assert fault is not None and fault.startswith(fragment), fault


def test_panel_payload_a_seat_that_declares_it_did_not_run_owes_no_findings():
    assert RA.payload_fault(RD.P_PANEL, {RA.VACUOUS_FIELD: True}, "code-reviewer") is None
    assert RA.payload_fault(RD.P_PANEL, {"findings": []}, "code-reviewer") is None


def test_panel_payload_a_non_boolean_never_ran_flag_is_named():
    """`_fold_panel` tests the flag with `is True`, so a truthy non-boolean silently means "this
    seat ran" — the seat then counts toward certification."""
    fault = RA.payload_fault(RD.P_PANEL, {"findings": [], RA.VACUOUS_FIELD: "yes"}, "code-reviewer")
    assert fault == "`%s` is str, not a boolean" % RA.VACUOUS_FIELD


def test_panel_vacuous_flag_marks_a_seat_never_ran(tmp_path):
    """Behavioural pin for `VACUOUS_FIELD`: a seat whose payload carries the flag under THIS key
    folds never-ran through the real driver. Binding the name to `dispatch_outcome.REASON_VACUOUS`
    (so the module carries no outcome-token literal) can never drift onto a key the fold ignores
    without this test going red."""
    d, n, state = _at(tmp_path, RD.P_PANEL)
    envelopes = [_result_env(dim, {"findings": []}) for dim in RD.DIMENSIONS
                 if dim != "premortem-reviewer"]
    envelopes.append(_result_env("premortem-reviewer",
                                 {"findings": [], RA.VACUOUS_FIELD: True}))
    artifact, reason = RA.assemble(RD.P_PANEL, envelopes, state, state["config"])
    assert reason is None
    assert RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"], artifact)["ok"]
    ok, after = RD.load_state(d)
    assert after["rounds"]["1"]["vacuousSeats"] == ["premortem-reviewer"]
    assert after["rounds"]["1"]["seatStatus"]["premortem-reviewer"] == "missing"
    assert after["fullPanelRan"] is False


@pytest.mark.parametrize("payload,fragment", [
    ({}, "`verdicts` is missing"),
    ({"verdicts": {}}, "`verdicts` is dict, not a list"),
    ({"verdicts": [{"verdict": "CONFIRMED", "findingId": "v0"}]},
     "apply_verdicts keys on `id`"),
    ({"verdicts": [{"id": "v0", "verdict": "MAYBE"}]}, "`verdicts[0].verdict` is 'MAYBE'"),
    ({"verdicts": [{"id": "v0", "verdict": "REFUTED", "reason": 3}]},
     "`verdicts[0].reason` is int, not a string"),
])
def test_verifier_payload_faults(payload, fragment):
    fault = RA.payload_fault(RD.P_VERIFIERS, payload, "verifier:f.py:0")
    assert fault is not None and fragment in fault, fault


@pytest.mark.parametrize("payload,fragment", [
    ({}, "`grouping` is missing"),
    ({"grouping": {}}, "`grouping` is dict, not a list"),
    ({"grouping": [{"group_id": "g"}]}, "`grouping`[0].member_ids is NoneType"),
    ({"grouping": [{"member_ids": []}]}, "`grouping`[0].member_ids is list, not a non-empty list"),
    ({"grouping": [{"member_ids": [3]}]}, "`grouping`[0].member_ids[0] is int"),
])
def test_synthesis_payload_faults(payload, fragment):
    fault = RA.payload_fault(RD.P_SYNTHESIS, payload, RA.SEAT_SYNTHESIS)
    assert fault is not None and fragment in fault, fault


def test_synthesis_payload_none_grouping_is_a_real_answer():
    assert RA.payload_fault(RD.P_SYNTHESIS, {"grouping": None}, RA.SEAT_SYNTHESIS) is None


@pytest.mark.parametrize("payload,fragment", [
    ({}, "`fixes` is missing"),
    ({"fixes": {}}, "`fixes` is dict, not a list"),
    ({"fixes": [], "escalated": "yes"}, "`escalated` is str, not a boolean"),
    ({"fixes": [], "headDiff": 3}, "`headDiff` is int, not a string"),
    ({"fixes": [], "headDiffPath": "relative/head.diff"}, "is not an absolute path"),
    ({"fixes": [], "coverageDecisions": ["x"]}, "`coverageDecisions`[0] is str"),
])
def test_fixer_payload_faults(payload, fragment):
    fault = RA.payload_fault(RD.P_FIXER, payload, RA.SEAT_FIXER)
    assert fault is not None and fragment in fault, fault


def test_verify_payload_fault_delegates_to_the_drivers_own_guard():
    """The adapter must never accept a `result` token the submit path refuses — so it asks the
    driver's own guard rather than keeping a second copy of the vocabulary."""
    for bad in ({}, {"result": "passed"}, {"passed": True}):
        assert RA.payload_fault(RD.P_VERIFY, bad, RA.SEAT_VERIFY) == RD.verify_result_fault(bad)
    for token in RD._VERIFY_RESULTS:
        assert RA.payload_fault(RD.P_VERIFY, {"result": token}, RA.SEAT_VERIFY) is None
    assert "`exit` is str, not an integer" in RA.payload_fault(
        RD.P_VERIFY, {"result": "pass", "exit": "0"}, RA.SEAT_VERIFY)


def test_new_issue_ruling_is_a_real_member_of_the_audits_enum():
    """The module names ONE member of `audits.AUDIT_RULINGS` (the enum itself is imported, never
    hand-copied). This holds that name equal to a real member so a rename cannot leave the
    new-issue rule pointed at a token nothing produces."""
    assert RA.RULING_NEW_ISSUE in audits.AUDIT_RULINGS


@pytest.mark.parametrize("payload,fragment", [
    ({"ruling": audits.AUDIT_RULINGS[0], "reason": "r"}, "`id` is NoneType"),
    ({"id": "other", "ruling": audits.AUDIT_RULINGS[0], "reason": "r"},
     "`id` is 'other' but this seat is"),
    ({"id": "f.py::t", "ruling": "fixed", "reason": "r"}, "`ruling` is 'fixed'"),
    ({"id": "f.py::t", "ruling": None, "reason": "r"}, "`ruling` is None"),
    ({"id": "f.py::t", "ruling": RA.RULING_NEW_ISSUE, "reason": "r"},
     "`newIssues` carries no usable issue object"),
    ({"id": "f.py::t", "ruling": RA.RULING_NEW_ISSUE, "reason": "r",
      "newIssue": "found another"}, "`newIssue` (singular)"),
    ({"id": "f.py::t", "ruling": audits.AUDIT_RULINGS[0], "reason": "r", "evidence": 3},
     "`evidence` is int, not a string"),
])
def test_audit_payload_faults(payload, fragment):
    fault = RA.payload_fault(RD.P_AUDITS, payload, "f.py::t")
    assert fault is not None and fragment in fault, fault


@pytest.mark.parametrize("ruling", audits.AUDIT_RULINGS)
def test_audit_payload_requires_a_reason_on_every_ruling(ruling):
    """A ruling with no grounds is the unproven claim the audit fold exists to reject. Record time
    is where it is still a cheap re-dispatch away from being right."""
    payload = {"id": "f.py::t", "ruling": ruling}
    if ruling == RA.RULING_NEW_ISSUE:
        payload["newIssues"] = [{"title": "n", "file": "f.py", "line": 1, "severity": "Minor"}]
    for reasonless in (dict(payload), dict(payload, reason=""), dict(payload, reason="   "),
                       dict(payload, reason=None), dict(payload, reason=3)):
        fault = RA.payload_fault(RD.P_AUDITS, reasonless, "f.py::t")
        assert fault is not None, ("a %s ruling with no usable reason must be refused at record "
                                   "time, got None for %r" % (ruling, reasonless))
        assert "`reason` is missing or blank" in fault, fault
    ok = dict(payload, reason="the fix resolves it")
    assert RA.payload_fault(RD.P_AUDITS, ok, "f.py::t") is None


def test_audit_payload_reason_predicate_is_the_folds_own():
    """Same predicate as the fold, never a second copy of the rule."""
    for reason in ("r", " r ", "", "   ", None, 3, []):
        fault = RA.payload_fault(
            RD.P_AUDITS, {"id": "i", "ruling": audits.AUDIT_RULINGS[1], "reason": reason}, "i")
        assert (fault is None) == audits.has_usable_reason(reason), (reason, fault)


# =============================================================================
# provenance — trusted manifest only
# =============================================================================

def test_ran_manifest_comes_only_from_the_dispatch_manifest_never_the_seat_echo(tmp_path):
    """A seat envelope's `vendor` is a claimant-controlled ADVISORY echo. With no orchestrator
    dispatch record there is NO trusted provenance, so the artifact carries no manifest — the
    driver's provenance-unavailable disclosure is what must fire."""
    _d, _n, state = _at(tmp_path, RD.P_PANEL)
    envelopes = [_result_env(dim, {"findings": []}, vendor="codex") for dim in RD.DIMENSIONS]
    artifact, reason = RA.assemble(RD.P_PANEL, envelopes, state, state["config"],
                                   dispatch_manifest=None)
    assert reason is None
    assert "ranManifest" not in artifact, (
        "a seat's own vendor echo must NEVER populate the trusted ran manifest")
    assert artifact["provenance"]["dispatchManifestUnavailable"] is True


def test_ran_manifest_uses_the_manifest_and_discloses_a_disagreeing_echo(tmp_path):
    _d, _n, state = _at(tmp_path, RD.P_PANEL)
    envelopes = [_result_env(dim, {"findings": []}, vendor="cursor") for dim in RD.DIMENSIONS]
    manifest = {dim: {"vendor": "codex", "model": "gpt-5", "engine": "codex"}
                for dim in RD.DIMENSIONS}
    artifact, reason = RA.assemble(RD.P_PANEL, envelopes, state, state["config"],
                                   dispatch_manifest=manifest)
    assert reason is None
    assert artifact["ranManifest"] == {dim: "codex" for dim in RD.DIMENSIONS}, (
        "the manifest governs; the echo is advisory")
    mismatch = artifact["provenance"]["vendorEchoMismatch"]
    assert {m["seat"] for m in mismatch} == set(RD.DIMENSIONS)
    assert all(m["echo"] == "cursor" and m["manifest"] == "codex" for m in mismatch)


def test_collection_manifest_comes_only_from_the_dispatch_manifest(tmp_path):
    d, n, state = _at(tmp_path, RD.P_AUDITS,
                      respond=_responder(round1_findings=_A_FINDING, head=HEAD_NEW_SURFACE))
    targets = n["payload"]["targets"]
    envelopes = [_result_env(t["id"], {"id": t["id"], "ruling": audits.AUDIT_RULINGS[0],
                                       "reason": "r", "auditorVendor": t.get("auditorVendor")},
                             vendor=t.get("auditorVendor")) for t in targets]
    artifact, reason = RA.assemble(RD.P_AUDITS, envelopes, state, state["config"],
                                   dispatch_manifest=None)
    assert reason is None
    assert "collectionManifest" not in artifact, (
        "an auditor's own vendor echo must NEVER authenticate its own discharge")
    # And the fold agrees: unauthenticated -> not-discharged.
    assert RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"], artifact)["ok"]
    ok, after = RD.load_state(d)
    outcomes = after["auditRounds"][-1]["outcomes"]
    assert outcomes and all(o["ruling"] == audits.AUDIT_RULINGS[1] for o in outcomes), outcomes
    assert any(dec["kind"] == "audit-provenance-fail" for dec in after["decisions"])


def test_manifest_entry_without_a_usable_vendor_is_disclosed_not_invented(tmp_path):
    _d, _n, state = _at(tmp_path, RD.P_PANEL)
    envelopes = [_result_env(dim, {"findings": []}, vendor="codex") for dim in RD.DIMENSIONS]
    manifest = {dim: "codex" for dim in RD.DIMENSIONS}      # bare strings, not entry objects
    artifact, reason = RA.assemble(RD.P_PANEL, envelopes, state, state["config"],
                                   dispatch_manifest=manifest)
    assert reason is None
    assert "ranManifest" not in artifact
    assert artifact["provenance"]["dispatchManifestEntryUnusable"] == list(RD.DIMENSIONS)


def test_seat_map_comes_from_state_and_is_omitted_when_empty(tmp_path):
    _d, _n, state = _at(tmp_path, RD.P_PANEL)
    envelopes = [_result_env(dim, {"findings": []}) for dim in RD.DIMENSIONS]
    artifact, reason = RA.assemble(RD.P_PANEL, envelopes, state, state["config"])
    assert reason is None and "seatMap" not in artifact
    state["seatMap"] = {"seats": {"code-reviewer": {"vendor": "codex"}}}
    artifact, reason = RA.assemble(RD.P_PANEL, envelopes, state, state["config"])
    assert reason is None and artifact["seatMap"] == state["seatMap"]


def test_canary_absent_omits_the_key_and_a_single_dict_is_tolerated(tmp_path):
    _d, _n, state = _at(tmp_path, RD.P_PANEL)
    envelopes = [_result_env(dim, {"findings": []}) for dim in RD.DIMENSIONS]
    artifact, reason = RA.assemble(RD.P_PANEL, envelopes, state, state["config"])
    assert reason is None and "canaryResult" not in artifact
    probe = {"engine": "codex", "engaged": True}
    artifact, reason = RA.assemble(RD.P_PANEL, envelopes, state, state["config"], canary=probe)
    assert reason is None and artifact["canaryResult"] == [probe]


def test_canary_is_a_list_one_probe_per_vendor(tmp_path):
    """`canary_liveness` judges each cross-vendor vendor independently and needs a probe whose
    `engine` matches; `seat_canary probe` emits ONE object per invocation, so the adapter carries
    the aggregated LIST."""
    _d, _n, state = _at(tmp_path, RD.P_PANEL)
    envelopes = [_result_env(dim, {"findings": []}) for dim in RD.DIMENSIONS]
    probes = [{"engine": "codex", "engaged": True}, {"engine": "cursor", "engaged": True}]
    artifact, reason = RA.assemble(RD.P_PANEL, envelopes, state, state["config"], canary=probes)
    assert reason is None and artifact["canaryResult"] == probes


# =============================================================================
# durability — the fixer head diff
# =============================================================================

def test_fixer_payload_refuses_caller_head_diff_store_path(tmp_path):
    """`headDiffStorePath` is driver-owned — a caller cannot inject a trusted store path."""
    store = tmp_path / "evil.diff"
    store.write_text(HEAD, encoding="utf-8")
    payload = {"fixes": [], "headDiffStorePath": str(store)}
    fault = RA.payload_fault(RD.P_FIXER, payload, RA.SEAT_FIXER, record_boundary=True)
    assert fault is not None
    assert "headDiffStorePath" in fault and "driver-owned" in fault
    # A/B: headDiffPath alone is still accepted
    caller = tmp_path / "caller-head.diff"
    caller.write_text(HEAD, encoding="utf-8")
    assert RA.payload_fault(RD.P_FIXER, {"fixes": [], "headDiffPath": str(caller)},
                            RA.SEAT_FIXER) is None


def test_fixer_head_diff_path_points_at_the_immutable_store_copy(tmp_path):
    """`_resolve_head_diff` opens the path at FOLD time, so a caller-controlled path can change
    between record and fold. The store copy is the one that cannot."""
    d = str(tmp_path / "session")
    os.makedirs(d)
    pend = RD.new_state(_cfg())
    pend["round"] = 1
    attempt = 0
    seat = RA.SEAT_FIXER
    skey = RR.storage_key(seat)
    store_copy = RR.store_path(d, 1, RD.P_FIXER, skey, attempt)
    os.makedirs(os.path.dirname(store_copy), exist_ok=True)
    headdiff = os.path.join(os.path.dirname(store_copy), "%s.a%d.headdiff" % (skey, attempt))
    with open(headdiff, "w", encoding="utf-8") as fh:
        fh.write(HEAD)
    payload = {"fixes": [], "headDiffStorePath": headdiff}
    env = _result_env(seat, payload)
    env.update({"round": 1, "phase": RD.P_FIXER, "attempt": attempt})
    artifact, reason = RA.assemble(RD.P_FIXER, [env], pend, _cfg(), session_dir=d)
    assert reason is None
    assert artifact["headDiffPath"] == headdiff
    assert "headDiffStorePath" not in artifact
    assert artifact["provenance"]["headDiffPathSource"] == "store"


def test_fixer_rejects_an_untrusted_head_diff_store_path(tmp_path):
    d = str(tmp_path / "session")
    os.makedirs(d)
    caller = tmp_path / "caller-head.diff"
    caller.write_text(HEAD, encoding="utf-8")
    skey = RR.storage_key(RA.SEAT_FIXER)
    lookalike = os.path.join("/attacker", "round-1", "seats", RD.P_FIXER,
                             "%s.a0.headdiff" % skey)
    payload = {"fixes": [], "headDiffPath": str(caller), "headDiffStorePath": lookalike}
    assert RA.payload_fault(RD.P_FIXER, payload, RA.SEAT_FIXER, record_boundary=True) is not None
    env = _result_env(RA.SEAT_FIXER, payload)
    env.update({"round": 1, "phase": RD.P_FIXER, "attempt": 0})
    artifact, reason = RA.assemble(RD.P_FIXER, [env], {}, {}, session_dir=d)
    assert artifact is None and reason == "head-diff-store-path-untrusted"


def test_fixer_head_diff_path_without_a_store_copy_is_disclosed(tmp_path):
    caller = tmp_path / "caller-head.diff"
    caller.write_text(HEAD, encoding="utf-8")
    payload = {"fixes": [], "headDiffPath": str(caller)}
    artifact, reason = RA.assemble(RD.P_FIXER, [_result_env(RA.SEAT_FIXER, payload)], {}, {})
    assert reason is None
    assert artifact["headDiffPath"] == str(caller)
    assert artifact["provenance"]["headDiffPathSource"] == "caller-path-no-store-copy"


def test_fixer_store_path_head_diff_folds_through_the_real_driver(tmp_path):
    """End to end: the driver-written store path the adapter emits is the one the fold reads."""
    d, n, state = _at(tmp_path, RD.P_FIXER)
    skey = RR.storage_key(RA.SEAT_FIXER)
    store_copy = RR.store_path(d, n["round"], RD.P_FIXER, skey, n["attempt"])
    headdiff = os.path.join(os.path.dirname(store_copy), "%s.a%d.headdiff" % (skey, n["attempt"]))
    os.makedirs(os.path.dirname(headdiff), exist_ok=True)
    with open(headdiff, "w", encoding="utf-8") as fh:
        fh.write(HEAD)
    payload = {"fixes": [], "headDiffStorePath": headdiff}
    env = _result_env(RA.SEAT_FIXER, payload)
    env.update({"round": n["round"], "phase": RD.P_FIXER, "attempt": n["attempt"]})
    artifact, reason = RA.assemble(RD.P_FIXER, [env], state, state["config"], session_dir=d)
    assert reason is None
    assert RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"], artifact)["ok"]
    ok, after = RD.load_state(d)
    assert after["headDiff"] == HEAD
    assert after["rounds"]["1"]["headDiffSource"] == "path"
    assert after["rounds"]["1"]["adapterProvenance"]["byPhase"][RD.P_FIXER]["headDiffPathSource"] == "store"


# =============================================================================
# payload_contract — conformance with checkers
# =============================================================================

_CONTRACT_PHASES = tuple(p for p in RA.ADAPTER_PHASES if p in RA._PAYLOAD_CHECKERS)

_SEAT_KEYS = {
    RD.P_PANEL: "code-reviewer",
    RD.P_VERIFIERS: "verifier:f.py:0",
    RD.P_SYNTHESIS: RA.SEAT_SYNTHESIS,
    RD.P_GAPSWEEP: RA.SEAT_GAPSWEEP,
    RD.P_SCOPED: RA.SEAT_SCOPED,
    RD.P_VERIFY: RA.SEAT_VERIFY,
    RD.P_FIXER: RA.SEAT_FIXER,
    RD.P_AUDITS: "f.py::t",
}


def _minimal_payload_for_contract(phase, contract, seat_key):
    payload = {}
    for field in contract.get("required") or []:
        enums = contract.get("enums") or {}
        if field in enums:
            payload[field] = enums[field][0]
        elif field == "findings":
            payload[field] = []
        elif field == "verdicts":
            payload[field] = [{"id": "v0", "verdict": verification.VERDICTS[0]}]
        elif field == "grouping":
            payload[field] = None
        elif field == "fixes":
            payload[field] = []
        elif field == "id":
            payload[field] = seat_key
        elif field == "ruling":
            payload[field] = audits.AUDIT_RULINGS[0]
        elif field == "reason":
            payload[field] = "grounds"
        else:
            payload[field] = "x"
    if phase == RD.P_PANEL and "findings" not in payload:
        payload[RA.VACUOUS_FIELD] = True
    return payload


@pytest.mark.parametrize("phase", _CONTRACT_PHASES)
def test_payload_contract_minimal_payload_accepted(phase):
    contract, reason = RA.payload_contract(phase)
    assert reason is None, reason
    seat_key = _SEAT_KEYS[phase]
    payload = _minimal_payload_for_contract(phase, contract, seat_key)
    assert RA.payload_fault(phase, payload, seat_key) is None


@pytest.mark.parametrize("phase", _CONTRACT_PHASES)
def test_payload_contract_required_keys_are_necessary(phase):
    contract, reason = RA.payload_contract(phase)
    assert reason is None, reason
    seat_key = _SEAT_KEYS[phase]
    base = _minimal_payload_for_contract(phase, contract, seat_key)
    for field in contract.get("required") or []:
        payload = dict(base)
        del payload[field]
        fault = RA.payload_fault(phase, payload, seat_key)
        assert fault is not None, (
            "dropping required %r must be refused for %s" % (field, phase))


def test_payload_contract_unknown_phase():
    contract, reason = RA.payload_contract("no-such-phase")
    assert contract == {} and reason == "unknown-phase:no-such-phase"


def test_payload_contract_every_checker_phase_has_data():
    for phase in RA._PAYLOAD_CHECKERS:
        contract, reason = RA.payload_contract(phase)
        assert reason is None, reason
        assert isinstance(contract.get("required"), list)
        assert isinstance(contract.get("optional"), list)
        assert isinstance(contract.get("enums"), dict)


def test_payload_contract_deep_copy_isolates_nested_mutation():
    phase = RD.P_AUDITS
    contract1, reason = RA.payload_contract(phase)
    assert reason is None
    contract1["required"].append("__mutated__")
    contract1["optional"].append("__mutated__")
    for values in contract1["enums"].values():
        values.append("__mutated__")
    contract1["conditional"]["__mutated__"] = True
    contract2, reason2 = RA.payload_contract(phase)
    assert reason2 is None
    assert "__mutated__" not in contract2["required"]
    assert "__mutated__" not in contract2["optional"]
    for values in contract2["enums"].values():
        assert "__mutated__" not in values
    assert "__mutated__" not in contract2["conditional"]
