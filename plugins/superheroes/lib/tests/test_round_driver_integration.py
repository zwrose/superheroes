#!/usr/bin/env python3
"""REAL-PATH integration tests for the #723 record layer: the REAL `round_driver` driving the REAL
`round_adapters`, over a REAL session dir, with NO stub and NO monkeypatch of the adapter module
anywhere in this file.

WHY THIS FILE EXISTS. `test_round_driver_advance.py` substitutes `round_adapters` through
`sys.modules` (legitimately — it tests the driver layer in isolation). That substitution is also
what let the driver→adapter seam ship BROKEN and GREEN: `_advance_locked` handed `assemble` a
`{seat: envelope}` MAPPING while the adapter's contract is a LIST of envelopes, so every phase in
the real path refused `assemble-refused` while 526 tests passed. A stubbed seam proves the driver's
own bookkeeping; it can prove NOTHING about the two modules agreeing. This module is the real-path
home, and `test_adapter_module_is_not_stubbed_in_this_module` is the fence that keeps it one.

Everything here drives the session the way the orchestrator does: land a seat envelope in the
LANDING area, `record-result` it into the durable store, then `advance` — lock, reconcile, sweep,
completeness, assemble, fold, emit. No `cmd_submit` is ever called by hand.
"""
import json
import os
import subprocess
import sys
import time

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

# PLAIN imports, not importlib side-loads: the driver imports `round_adapters` at CALL time through
# `sys.modules`, so the module objects this test asserts about must be the very ones the driver
# reaches. A side-loaded copy would let a stub sit in `sys.modules` unnoticed.
import engine_adapter  # noqa: E402
import engine_dispatch  # noqa: E402
import payload_contracts  # noqa: E402
import review_findings_schema  # noqa: E402
import round_adapters  # noqa: E402
import round_certification  # noqa: E402
import round_driver  # noqa: E402
import round_records  # noqa: E402
import sanitized_view  # noqa: E402
import session_contract  # noqa: E402

# =============================================================================================
# the diffs — a BIG round-1 diff (so the gap-sweep phase is on the path) and its post-fix head
# =============================================================================================

# >20 changed files ⇒ `delta_surface.shard_plan` says big ⇒ `_fold_synthesis` routes through
# `dispatch-gap-sweep`, which is otherwise unreachable and would leave that adapter unexercised.
FILES = ["src/f%02d.py" % i for i in range(21)]
FIXED_FILE = FILES[0]
NEW_SURFACE_FILE = "src/new_surface.py"


def _section(path, third):
    """One file's unified-diff section. Anchorable RIGHT-side lines are 1..4."""
    return ("diff --git a/%s b/%s\n" % (path, path)
            + "index 1111111..2222222 100644\n"
            + "--- a/%s\n" % path
            + "+++ b/%s\n" % path
            + "@@ -1,2 +1,4 @@\n"
            + " alpha\n"
            + "+beta\n"
            + "+%s\n" % third
            + " delta\n")


REVIEWED_DIFF = "".join(_section(p, "gamma") for p in FILES)
# The post-fix head: the fixed file's section CHANGED (so `split_fix_surface` attributes it to the
# fix) plus one file present only on the head side (the NEW surface the scoped finder scans).
HEAD_DIFF = ("".join(_section(p, "gamma-fixed" if p == FIXED_FILE else "gamma") for p in FILES)
             + _section(NEW_SURFACE_FILE, "fresh"))

SEAT_MAP = {"seats": {dim: {"vendor": "claude", "model": "sonnet-5", "engine": "claude"}
                      for dim in round_driver.DIMENSIONS}}
FINDING_SEAT = "code-reviewer"
_FAKE_GIT_HEAD = "a" * 40
_WRITE_META_HEAD = object()


def _blocking_finding(title, line):
    return {"file": FIXED_FILE, "line": line, "title": title, "severity": "Important",
            "detail": "%s at %s:%d" % (title, FIXED_FILE, line)}


# =============================================================================================
# session helpers
# =============================================================================================

def _cfg(**over):
    base = {"leg": "code", "vendors": ["claude"], "diff": REVIEWED_DIFF, "fixerVendor": "claude",
            "verifyCommand": "none", "seatMap": SEAT_MAP}
    base.update(over)
    return base


def _state(session_dir):
    ok, state = round_driver.load_state(session_dir)
    assert ok, state
    return state


def _session_id(session_dir):
    with open(os.path.join(session_dir, round_records.META_FILE), encoding="utf-8") as fh:
        return json.load(fh)["sessionId"]


def _fake_git(gitdir):
    """The ONE git seam `_publish_sidecar` reads through — injected so no test here touches the
    developer's real checkout."""
    def run(cwd, *args):
        if args[:2] == ("rev-parse", "--absolute-git-dir"):
            return gitdir
        if args == ("rev-parse", "HEAD"):
            return _FAKE_GIT_HEAD
        if args[:3] == ("rev-parse", "--abbrev-ref", "HEAD"):
            return "feature/x"
        if args[0] == "rev-parse" and "--verify" in args:
            return "b" * 40
        if args[:2] == ("remote", "get-url"):
            return "github.com/o/r"
        return None
    return run


def _anchor_hashes(session_dir, state, pend, seat, occurrence=0):
    """The emission-time anchor an envelope must echo (`round_records._anchor_check`)."""
    anchor = round_driver._orders_anchor(state, session_dir, pend["round"], pend["phase"],
                                         pend["attempt"])
    if anchor is None:
        return round_records.NOT_EMITTED, round_records.NOT_EMITTED
    skey = round_records.storage_key(seat, occurrence)
    return anchor["manifestSha256"], (anchor.get("orders") or {}).get(
        skey, round_records.NOT_EMITTED)


def _execution_evidence(**over):
    evidence = {
        "source": "runner",
        "runnerNonce": "nonce-1",
        "recordDigest": "digest-1",
        "resultKind": "findings",
        "resultDigest": round_records.payload_sha256([]),
        "observation": {
            "tokens": None,
            "toolCalls": None,
            "stdoutBytes": 0,
            "wallSeconds": 0.0,
            "source": "none",
            "read": "unknown",
            "telemetry": "none",
        },
    }
    evidence.update(over)
    return evidence


def _execution_evidence_for_payload(payload, source="runner"):
    observation = {
        "tokens": None,
        "toolCalls": None,
        "stdoutBytes": 0,
        "wallSeconds": 0.0,
        "source": "none",
        "read": "unknown",
        "telemetry": "none",
    }
    for kind in engine_adapter.REVIEW_RESULT_KINDS + ("fixes", "result"):
        if kind in payload:
            carried, subject = session_contract.evidence_digest_subject(payload, kind)
            result_digest = (round_records.payload_sha256(subject)
                             if carried else round_records.payload_sha256(payload[kind]))
            return _execution_evidence(
                resultKind=kind,
                resultDigest=result_digest,
                observation=observation,
                source=source,
            )
    return _execution_evidence(observation=observation, source=source)


def _land(session_dir, state, pend, seat, payload, occurrence=0):
    """Write ONE seat's envelope into the LANDING area (what the host does)."""
    manifest_sha, order_sha = _anchor_hashes(session_dir, state, pend, seat)
    schema = round_records.seat_result_schema_for_state_version(state.get("schemaVersion"))
    if schema is None:
        schema = round_records.SEAT_RESULT_SCHEMA
    envelope = {
        "schema": schema,
        "session": _session_id(session_dir),
        "round": pend["round"],
        "phase": pend["phase"],
        "seat": seat,
        "attempt": pend["attempt"],
        "vendor": "claude",
        "model": "sonnet-5",
        "dispatchRef": manifest_sha,
        "orderSha256": order_sha,
        "manifestSha256": manifest_sha,
        "recordedAt": "2026-08-07T00:00:00",
        "payloadSha256": round_records.payload_sha256(payload),
        "payload": payload,
    }
    if schema == round_records.SEAT_RESULT_SCHEMA_V2:
        evidence_source = _auditor_vendor_for(state)(seat)
        evidence = _execution_evidence_for_payload(payload, source=evidence_source)
        envelope["executionEvidence"] = evidence
        envelope["provenance"] = round_records.PROVENANCE_HAND_LANDED
        envelope["envelopeSha256"] = round_records.envelope_sha256(payload, evidence)
    if occurrence:
        envelope["occurrence"] = occurrence
    path = round_records.landing_path(session_dir, pend["round"], pend["phase"],
                                      round_records.storage_key(seat, occurrence),
                                      pend["attempt"])
    round_records.atomic_write_json(path, envelope)
    return path


def _record(session_dir, seat, occurrence=0):
    """`record-result` for one roster slot. Occurrence 0 goes through the PLAIN call — the shape the
    CLI makes when no seat key repeats (`--occurrence` defaults to 0)."""
    if occurrence:
        return round_driver.cmd_record_result(session_dir, seat, occurrence=occurrence)
    return round_driver.cmd_record_result(session_dir, seat)


def _write_dispatch_manifest(session_dir, pend, slots, vendor_for):
    """The ORCHESTRATOR's out-of-band dispatch manifest — the ONLY provenance the adapter trusts."""
    manifest = {seat: {"vendor": vendor_for(seat), "model": "sonnet-5", "engine": "claude"}
                for seat, _occurrence in slots}
    round_records.atomic_write_json(
        round_records.dispatch_manifest_path(session_dir, pend["round"], pend["phase"],
                                             pend["attempt"]),
        manifest)


# =============================================================================================
# per-phase seat payloads — what a real seat would land
# =============================================================================================

def _cluster_for(pend, seat):
    key = seat[len(round_adapters.VERIFIER_SEAT_PREFIX):]
    for cluster in (pend.get("payload") or {}).get("clusters") or []:
        if cluster.get("key") == key:
            return cluster
    raise AssertionError("no cluster %r in the pending payload" % key)


def _payload_for(session_dir, state, pend, seat, panel_findings, head_diff_path):
    phase = pend["phase"]
    if phase == round_driver.P_PANEL:
        findings = panel_findings if (seat == FINDING_SEAT and state["round"] == 1) else []
        return {"findings": [dict(f) for f in findings], "confidence": "high",
                "tier": round_driver.DEEP}
    if phase == round_driver.P_VERIFIERS:
        cluster = _cluster_for(pend, seat)
        return {"verdicts": [{"id": f["id"], "verdict": "CONFIRMED", "severity": "Important",
                              "reason": "reproduced the cited line",
                              "evidence": "read %s" % f.get("file")}
                             for f in cluster.get("findings") or []]}
    if phase == round_driver.P_SYNTHESIS:
        return {"grouping": None}
    if phase in (round_driver.P_GAPSWEEP, round_driver.P_SCOPED):
        return {"findings": []}
    if phase == round_driver.P_FIXER:
        return {"fixes": [{"file": FIXED_FILE, "summary": "guard restored"}],
                "escalated": False, "headDiffPath": head_diff_path}
    if phase == round_driver.P_VERIFY:
        return {"result": "pass", "command": "none", "exit": 0}
    if phase == round_driver.P_AUDITS:
        return {"id": seat, "ruling": "discharged", "auditorVendor": "claude",
                "reason": "re-read the fixed hunk; the cited defect is gone"}
    raise AssertionError("no payload for phase %r" % phase)


def _auditor_vendor_for(state):
    targets = state.get("_auditTargets") or []
    by_id = {t.get("id"): t.get("auditorVendor") for t in targets if isinstance(t, dict)}
    return lambda seat: by_id.get(seat, "claude")


# =============================================================================================
# the driver harness — land, record, advance; never a hand `submit`
# =============================================================================================

def _assert_adapters_are_real():
    """The fence: this module drives the REAL adapter. A stub in `sys.modules` — the exact thing
    that hid the seam defect — fails here, at CALL time, not merely at import."""
    assert sys.modules.get("round_adapters") is round_adapters
    assert round_adapters.assemble.__module__ == "round_adapters"
    assert round_adapters.roster_for.__module__ == "round_adapters"


def _slots_of(roster):
    """[(seat, occurrence)] — the roster expanded so a REPEATED seat key stays addressable."""
    seen = {}
    slots = []
    for seat in roster:
        occurrence = seen.get(seat, 0)
        seen[seat] = occurrence + 1
        slots.append((seat, occurrence))
    return slots


def _drive_one_phase(session_dir, gitdir, panel_findings, head_diff_path):
    """Land + record every roster slot of the pending phase, then `advance`. -> (phase, out)."""
    _assert_adapters_are_real()
    state = _state(session_dir)
    pend = state["pending"]
    phase = pend["phase"]
    assert phase in round_adapters.ADAPTER_PHASES, (
        "phase %r is not an adapter phase — this harness drives dispatch phases only" % phase)
    roster, reason = round_adapters.roster_for(phase, state, state.get("config") or {})
    assert reason is None, (phase, reason)
    slots = _slots_of(roster)
    _write_dispatch_manifest(session_dir, pend, slots, _auditor_vendor_for(state))
    for seat, occurrence in slots:
        payload = _payload_for(session_dir, state, pend, seat, panel_findings, head_diff_path)
        _land(session_dir, state, pend, seat, payload, occurrence=occurrence)
        out = _record(session_dir, seat, occurrence=occurrence)
        assert out["ok"], (phase, seat, occurrence, out)
    out = round_driver.cmd_advance(session_dir, git=_fake_git(gitdir))
    return phase, out


def _bootstrap(tmp_path, name="s", head_sha=_WRITE_META_HEAD, **cfg_over):
    session_dir = str(tmp_path / name)
    os.makedirs(session_dir, exist_ok=True)
    gitdir = str(tmp_path / (name + "-gitdir"))
    os.makedirs(gitdir, exist_ok=True)
    head_diff_path = str(tmp_path / (name + "-head.diff"))
    with open(head_diff_path, "w", encoding="utf-8") as fh:
        fh.write(HEAD_DIFF)
    out = round_driver.cmd_next(session_dir, _cfg(**cfg_over))
    assert out["ok"], out
    if head_sha is not None:
        if head_sha is _WRITE_META_HEAD:
            head_sha = _fake_git(gitdir)(session_dir, "rev-parse", "HEAD")
        meta_path = os.path.join(session_dir, round_records.META_FILE)
        meta = {}
        if os.path.exists(meta_path):
            with open(meta_path, encoding="utf-8") as fh:
                meta = json.load(fh)
        meta["headSha"] = head_sha
        with open(meta_path, "w", encoding="utf-8") as fh:
            json.dump(meta, fh, sort_keys=True)
            fh.write("\n")
    return session_dir, gitdir, head_diff_path


def _drive_to_terminal(session_dir, gitdir, panel_findings, head_diff_path, max_steps=24):
    """Drive the session through `advance` ALONE until it reaches a terminal. Returns the ordered
    list of phases that actually FOLDED."""
    folded = []
    for _ in range(max_steps):
        if _state(session_dir).get("terminal"):
            return folded
        before = _state(session_dir)["pending"]["phase"]
        phase, out = _drive_one_phase(session_dir, gitdir, panel_findings, head_diff_path)
        assert out["ok"], (phase, out)
        # the phase FOLDED — not merely "no exception": the driver says so, and the state moved
        assert out["folded"]["phase"] == phase, out
        assert _state(session_dir)["step"] != before, (phase, _state(session_dir)["step"])
        folded.append(phase)
    raise AssertionError("did not reach a terminal in %d steps: %s" % (max_steps, folded))


# =============================================================================================
# §1 the fence — this module drives the REAL adapter
# =============================================================================================

def test_adapter_module_is_not_stubbed_in_this_module():
    """A future author who stubs `round_adapters` back into this module fails HERE.

    Both halves matter: the object this module holds must be the one `sys.modules` hands the
    driver, and its functions must come from the real modules (a per-function patch leaves the
    module identity intact but re-hides the seam). The payload validator's real home is now
    `payload_contracts`; a stub of either module still fails here."""
    _assert_adapters_are_real()
    assert round_adapters.__name__ == "round_adapters"
    assert round_adapters.missing_policy.__module__ == "round_adapters"
    assert round_adapters.payload_fault.__module__ == "payload_contracts"
    assert round_adapters.payload_fault is payload_contracts.payload_fault
    # and the driver's own call-time lookup resolves to that same module
    assert round_driver._adapters() is round_adapters


# =============================================================================================
# §2 the seam — every adapter phase folds through the REAL adapter
# =============================================================================================

def test_advance_folds_the_panel_through_the_real_adapter(tmp_path):
    """The narrowest statement of the shipped defect: ONE phase, real driver, real adapter.

    Pre-fix this refuses `assemble-refused` with `envelopes-not-a-list:dict` — the driver handed the
    adapter a mapping. Nothing about the driver's own bookkeeping was wrong, which is exactly why a
    stubbed adapter could not see it."""
    session_dir, gitdir, head_path = _bootstrap(tmp_path)
    phase, out = _drive_one_phase(session_dir, gitdir,
                                  [_blocking_finding("missing bounds guard", 2)], head_path)
    assert phase == round_driver.P_PANEL
    assert out["ok"] is True, out
    assert out["folded"] == {"phase": round_driver.P_PANEL, "round": 1, "attempt": 0}
    assert out["nextAction"]["phase"] == round_driver.P_VERIFIERS
    assert _state(session_dir)["step"] == round_driver.P_VERIFIERS
    # the fold consumed the REAL adapter's artifact: the panel seat's finding is staged to verify
    assert [f.get("title") for f in _state(session_dir)["_toVerify"]] == ["missing bounds guard"]


def test_every_adapter_phase_folds_and_the_round_reaches_a_terminal_receipt(tmp_path):
    """EVERY phase in `round_adapters.ADAPTER_PHASES` folds through the real seam, and the session
    reaches its terminal receipt through `advance` alone — no hand `submit` anywhere."""
    session_dir, gitdir, head_path = _bootstrap(tmp_path)
    folded = _drive_to_terminal(session_dir, gitdir,
                                [_blocking_finding("missing bounds guard", 2)], head_path)

    unexercised = [p for p in round_adapters.ADAPTER_PHASES if p not in folded]
    assert not unexercised, ("phases that never folded through the real adapter: %s (folded: %s)"
                             % (unexercised, folded))

    state = _state(session_dir)
    assert state["terminal"] == "converged", state.get("certification")
    # a terminal receipt exists, validates, and carries the driver's own ran evidence
    with open(os.path.join(session_dir, round_driver.RECEIPT_FILE), encoding="utf-8") as fh:
        receipt = json.load(fh)
    ok, why = round_driver.validate_receipt(receipt)
    assert ok, why
    assert receipt["scriptRan"]["invocations"]
    # …and the whole session was driven by `advance`: the interleave fence never saw a hand submit
    assert state.get("_advanceUsed") is True
    assert state.get("_submitUsed") is None


def test_sweep_record_path_reaches_populated_terminal_receipt(tmp_path):
    """Run-level acceptance: record-result --sweep per phase, then advance, through terminal."""
    session_dir, gitdir, head_path = _bootstrap(tmp_path)

    def _drive_phase_with_sweep(panel_findings):
        _assert_adapters_are_real()
        state = _state(session_dir)
        pend = state["pending"]
        phase = pend["phase"]
        roster, reason = round_adapters.roster_for(phase, state, state.get("config") or {})
        assert reason is None, (phase, reason)
        slots = _slots_of(roster)
        _write_dispatch_manifest(session_dir, pend, slots, _auditor_vendor_for(state))
        for seat, occurrence in slots:
            payload = _payload_for(session_dir, state, pend, seat, panel_findings, head_path)
            _land(session_dir, state, pend, seat, payload, occurrence=occurrence)
        sweep = round_driver.cmd_record_result(session_dir, sweep=True)
        assert sweep["ok"] is True, (phase, sweep)
        recorded = sweep.get("recorded") or []
        assert sorted(recorded) == sorted(round_driver._slot_label(seat, occurrence)
                                          for seat, occurrence in slots), (phase, sweep, slots)
        for seat, occurrence in slots:
            spath = round_records.store_path(
                session_dir, pend["round"], phase,
                round_records.storage_key(seat, occurrence), pend["attempt"])
            assert os.path.exists(spath), (phase, seat, occurrence, spath)
        out = round_driver.cmd_advance(session_dir, git=_fake_git(gitdir))
        return phase, out

    folded = []
    for _ in range(24):
        if _state(session_dir).get("terminal"):
            break
        phase, out = _drive_phase_with_sweep(
            [_blocking_finding("missing bounds guard", 2)])
        assert out["ok"] is True, (phase, out)
        folded.append(phase)
    else:
        raise AssertionError("did not reach terminal: %s" % folded)

    state = _state(session_dir)
    assert state["terminal"] == "converged", state.get("certification")
    with open(os.path.join(session_dir, round_driver.RECEIPT_FILE), encoding="utf-8") as fh:
        receipt = json.load(fh)
    ok, why = round_driver.validate_receipt(receipt)
    assert ok, why
    assert receipt.get("rounds")
    assert receipt.get("certification") is not None
    assert receipt["scriptRan"]["byPhase"]


def test_advance_refuses_an_incomplete_roster_before_it_ever_assembles(tmp_path):
    """A/B against the folding path above: one seat short refuses by NAME, and the refusal is the
    completeness one — never a downstream adapter reason."""
    session_dir, gitdir, head_path = _bootstrap(tmp_path)
    state = _state(session_dir)
    pend = state["pending"]
    for seat in round_driver.DIMENSIONS[:2]:
        _land(session_dir, state, pend, seat,
              _payload_for(session_dir, state, pend, seat, [], head_path))
        assert _record(session_dir, seat)["ok"] is True
    out = round_driver.cmd_advance(session_dir, git=_fake_git(gitdir))
    assert out["ok"] is False
    assert out["reason"] == "incomplete-roster", out
    assert out["seats"] == sorted(round_driver.DIMENSIONS[2:]), out


# =============================================================================================
# §3 occurrence — two DISTINCT audit targets that legitimately share one id
# =============================================================================================

def _drive_to_phase(session_dir, gitdir, panel_findings, head_diff_path, phase,
                    max_steps=24):
    """Drive until `phase` is pending (folding every phase before it). Returns the folded list."""
    folded = []
    for _ in range(max_steps):
        state = _state(session_dir)
        assert not state.get("terminal"), "reached a terminal before %r: %s" % (phase, folded)
        if state["pending"]["phase"] == phase:
            return folded
        seen, out = _drive_one_phase(session_dir, gitdir, panel_findings, head_diff_path)
        assert out["ok"], (seen, out)
        folded.append(seen)
    raise AssertionError("never reached %r: %s" % (phase, folded))


def test_two_same_titled_targets_at_different_lines_one_discharged_sibling_not(tmp_path):
    """#915 headline regression: two same-titled findings at different lines get DISTINCT audit
    target ids. One seat's discharged ruling is recorded; the sibling arrives via record-missing.
    Assembled through round_adapters._assemble_audits and folded through _fold_audits, the unaudited
    sibling folds not-discharged — never silently discharged off the sibling's ruling."""
    session_dir, gitdir, head_path = _bootstrap(tmp_path, name="distinct-lines")
    findings = [_blocking_finding("unchecked index", 2), _blocking_finding("unchecked index", 3)]
    _drive_to_phase(session_dir, gitdir, findings, head_path, round_driver.P_AUDITS)

    state = _state(session_dir)
    targets = state["_auditTargets"]
    assert len(targets) == 2, targets
    assert targets[0]["id"] != targets[1]["id"], targets
    assert targets[0]["identity"] == targets[1]["identity"], targets
    tid0, tid1 = targets[0]["id"], targets[1]["id"]
    ident = targets[0]["identity"]

    roster, reason = round_adapters.roster_for(round_driver.P_AUDITS, state,
                                               state.get("config") or {})
    assert reason is None and roster == [tid0, tid1], roster

    pend = state["pending"]
    _write_dispatch_manifest(session_dir, pend, [(tid0, 0), (tid1, 0)], _auditor_vendor_for(state))
    _land(session_dir, state, pend, tid0,
          {"id": tid0, "ruling": "discharged", "auditorVendor": "claude",
           "reason": "re-read line 2; the defect is gone"})
    assert _record(session_dir, tid0)["ok"] is True
    out = round_driver.cmd_record_missing(session_dir, tid1, pend["attempt"], "forfeit")
    assert out["ok"] is True, out

    out = round_driver.cmd_advance(session_dir, git=_fake_git(gitdir))
    assert out["ok"] is True, out
    assert out["folded"]["phase"] == round_driver.P_AUDITS

    state_after = _state(session_dir)
    audits_round = state_after["auditRounds"][-1]
    assert [a["identity"] for a in audits_round["outcomes"]] == [ident, ident], audits_round
    outcome = state_after["_auditOutcome"]
    assert tid0 in outcome["discharged"], outcome
    assert tid1 in outcome["notDischarged"], outcome
    assert tid1 in outcome["unaudited"], outcome
    assert tid0 not in outcome["notDischarged"], outcome


def test_a_missing_second_occurrence_is_named_by_slot_not_by_seat(tmp_path):
    """Two same-location findings whose titles agree past the clamp yield distinct content-keyed ids; advance names the absent second target when only the first is recorded."""
    session_dir, gitdir, head_path = _bootstrap(tmp_path, name="collide-short")
    prefix = "unchecked index " + "x" * 160
    alpha_title = prefix + " alpha"
    beta_title = prefix + " beta"
    findings = [_blocking_finding(alpha_title, 2)]
    _drive_to_phase(session_dir, gitdir, findings, head_path, round_driver.P_AUDITS)
    state = _state(session_dir)
    alpha = _blocking_finding(alpha_title, 2)
    beta = _blocking_finding(beta_title, 2)
    assert session_contract.location_key(alpha) == session_contract.location_key(beta)
    dup = [alpha, beta]
    state["fixBatch"] = dup
    state["_auditTargets"] = round_driver._audit_targets(state, state.get("config") or {}, {})
    round_driver.save_state(session_dir, state)
    state = _state(session_dir)
    targets = state["_auditTargets"]
    assert len(targets) == 2 and targets[0]["id"] != targets[1]["id"], targets
    tid0, tid1 = targets[0]["id"], targets[1]["id"]
    pend = state["pending"]
    _write_dispatch_manifest(session_dir, pend, [(tid0, 0), (tid1, 0)], _auditor_vendor_for(state))
    _land(session_dir, state, pend, tid0,
          {"id": tid0, "ruling": "discharged", "reason": "re-read the hunk; the defect is gone"})
    assert _record(session_dir, tid0)["ok"] is True

    out = round_driver.cmd_advance(session_dir, git=_fake_git(gitdir))
    assert out["ok"] is False and out["reason"] == "incomplete-roster", out
    assert out["seats"] == [tid1], out


def test_record_missing_addresses_the_second_target(tmp_path):
    """`record-missing` on a distinct per-location id does not claim its sibling is absent."""
    session_dir, gitdir, head_path = _bootstrap(tmp_path, name="collide-missing")
    findings = [_blocking_finding("unchecked index", 2), _blocking_finding("unchecked index", 3)]
    _drive_to_phase(session_dir, gitdir, findings, head_path, round_driver.P_AUDITS)

    state = _state(session_dir)
    targets = state["_auditTargets"]
    tid0, tid1 = targets[0]["id"], targets[1]["id"]
    assert tid0 != tid1, targets
    pend = state["pending"]
    _land(session_dir, state, pend, tid0,
          {"id": tid0, "ruling": "discharged", "reason": "re-read the hunk; the defect is gone"})
    assert _record(session_dir, tid0)["ok"] is True
    out = round_driver.cmd_record_missing(session_dir, tid1, pend["attempt"], "forfeit")
    assert out["ok"] is True, out

    stored, err = round_records.read_json(out["storePath"])
    assert err is None and stored.get("seat") == tid1, (err, stored)
    other = round_records.store_path(session_dir, pend["round"], pend["phase"],
                                     round_records.storage_key(tid0, 0), pend["attempt"])
    kept, err = round_records.read_json(other)
    expected_schema = round_records.seat_result_schema_for_state_version(state.get("schemaVersion"))
    if expected_schema is None:
        expected_schema = round_records.SEAT_RESULT_SCHEMA
    assert err is None and kept["schema"] == expected_schema, (err, kept)


@pytest.mark.parametrize("occurrence", [2, 7])
def test_recording_an_occurrence_outside_the_roster_is_refused(tmp_path, occurrence):
    """A/B — occurrences 0 and 1 record fine (above); an occurrence the roster does not have is
    refused, never stored into a slot no fold will ever read."""
    session_dir, gitdir, head_path = _bootstrap(tmp_path, name="collide-beyond-%d" % occurrence)
    findings = [_blocking_finding("unchecked index", 2), _blocking_finding("unchecked index", 3)]
    _drive_to_phase(session_dir, gitdir, findings, head_path, round_driver.P_AUDITS)

    state = _state(session_dir)
    tid = state["_auditTargets"][0]["id"]
    pend = state["pending"]
    _land(session_dir, state, pend, tid,
          {"id": tid, "ruling": "discharged", "reason": "re-read the hunk; the defect is gone"},
          occurrence=occurrence)
    out = _record(session_dir, tid, occurrence=occurrence)
    assert out["ok"] is False and out["reason"] == "unknown-occurrence", out
    spath = round_records.store_path(session_dir, pend["round"], pend["phase"],
                                     round_records.storage_key(tid, occurrence), pend["attempt"])
    assert not os.path.exists(spath), spath
    lpath = round_records.landing_path(session_dir, pend["round"], pend["phase"],
                                       round_records.storage_key(tid, occurrence), pend["attempt"])
    assert os.path.exists(lpath), "record-result may leave the landing; ingest refused before store"
    out_missing = round_driver.cmd_record_missing(session_dir, tid, pend["attempt"], "forfeit",
                                                  occurrence=occurrence)
    assert out_missing["ok"] is False and out_missing["reason"] == "unknown-occurrence", out_missing
    assert os.path.exists(lpath), "record-missing must not write a landing when one already exists"


def test_driver_landing_envelope_schema_derives_from_state_version(tmp_path):
    """Each driver-landing producer mints schema from the session's schemaVersion."""
    from test_round_driver_advance import _result_envelope as advance_envelope
    from test_round_driver_records_cli import _result_envelope as records_cli_envelope

    session_dir, gitdir, head_path = _bootstrap(tmp_path, name="schema-derive")
    findings = [_blocking_finding("unchecked index", 2)]
    _drive_to_phase(session_dir, gitdir, findings, head_path, round_driver.P_PANEL)

    state = _state(session_dir)
    pend = state["pending"]
    expected = round_records.seat_result_schema_for_state_version(state.get("schemaVersion"))
    if expected is None:
        expected = round_records.SEAT_RESULT_SCHEMA
    seat = FINDING_SEAT
    payload = _payload_for(session_dir, state, pend, seat, findings, head_path)

    path = _land(session_dir, state, pend, seat, payload)
    landed, err = round_records.read_json(path)
    assert err is None, err
    assert landed["schema"] == expected

    cli_env = records_cli_envelope(session_dir, seat, payload=payload, pend=pend)
    assert cli_env["schema"] == expected

    adv_env = advance_envelope(session_dir, seat, payload=payload, pend=pend)
    assert adv_env["schema"] == expected

    if expected == round_records.SEAT_RESULT_SCHEMA_V2:
        for env in (landed, cli_env, adv_env):
            assert env["provenance"] == round_records.PROVENANCE_HAND_LANDED
            assert "envelopeSha256" in env
            assert "executionEvidence" in env


def _dispatch_observed_land(session_dir, state, pend, seat, payload, occurrence=0):
    manifest_sha, order_sha = _anchor_hashes(session_dir, state, pend, seat, occurrence)
    envelope = {
        "schema": round_records.SEAT_RESULT_SCHEMA_V2,
        "session": _session_id(session_dir),
        "round": pend["round"],
        "phase": pend["phase"],
        "seat": seat,
        "attempt": pend["attempt"],
        "vendor": "claude",
        "model": "sonnet-5",
        "dispatchRef": manifest_sha,
        "orderSha256": order_sha,
        "manifestSha256": manifest_sha,
        "recordedAt": "2026-01-01T00:00:00",
        "payloadSha256": round_records.payload_sha256(payload),
        "payload": payload,
        "provenance": round_records.PROVENANCE_DISPATCH_OBSERVED,
        "envelopeSha256": round_records.envelope_sha256(payload, None),
    }
    if occurrence:
        envelope["occurrence"] = occurrence
    path = round_records.landing_path(session_dir, pend["round"], pend["phase"],
                                      round_records.storage_key(seat, occurrence),
                                      pend["attempt"])
    round_records.atomic_write_json(path, envelope)
    return path


def _codex_item_completed(item_type, item_id="item_0", **item_extra):
    item = {"id": item_id, "type": item_type}
    item.update(item_extra)
    return json.dumps({"type": "item.completed", "item": item})


def _codex_event_stream(payload_text, *, action_items=1):
    lines = []
    for i in range(action_items):
        lines.append(_codex_item_completed("command_execution", "ce_%d" % i))
    lines.append(_codex_item_completed(
        "agent_message", "agent_msg", text=payload_text))
    lines.append(json.dumps({
        "type": "turn.completed",
        "usage": {
            "input_tokens": 100,
            "cached_input_tokens": 0,
            "output_tokens": 10,
            "reasoning_output_tokens": 0,
        },
    }))
    return "\n".join(lines)


def _execution_run_dir(tmp_path, order_path, panel_findings, echo_nonce="nonce-panel-e2e",
                       telemetry_shape="dispatch-observed"):
    """Build a runner run directory for dispatch-observed evidence tests.

    This run directory is a test double for the runner's own record of a real dispatch; the
    parsing of a real codex event stream is covered by the adapter's own tests
    (``test_engine_adapter.py``), not by this module.

    ``telemetry_shape`` selects the stdout/engine pairing:
    - ``dispatch-observed`` (default): codex engine with a JSONL event stream carrying at
      least one completed action item and the panel findings as the last ``agent_message``.
    - ``no-telemetry``: claude engine with plain JSON stdout from which no runner tool-call
      count can be derived.
    """
    run_dir = str(tmp_path / "dispatch-evidence-run")
    journal_root = str(tmp_path / "dispatch-journal-root")
    os.makedirs(journal_root, exist_ok=True)
    os.environ[engine_dispatch.JOURNAL_ROOT_ENV] = journal_root
    repo_root = str(tmp_path / "dispatch-evidence-repo")
    os.makedirs(repo_root, exist_ok=True)
    with open(os.path.join(repo_root, ".git"), "w", encoding="utf-8") as fh:
        fh.write("gitdir: /fake/worktree\n")
    view_path = str(tmp_path / "dispatch-evidence-view")
    os.makedirs(view_path, exist_ok=True)
    view_meta = {"headSha": "abc123fake", "stripped": [], "path": view_path}
    with open(order_path, encoding="utf-8") as fh:
        base_prompt = fh.read()
    notice = sanitized_view.sanitized_view_notice(view_meta, mode="review")
    fed_prompt = (
        engine_dispatch.ANTIHIJACK_PREAMBLE + notice + base_prompt + "\n\n"
        + review_findings_schema.example_prompt_block(echo_nonce) + "\n\n"
        + engine_adapter.REVIEW_RESULT_CONTRACT("findings")
    )
    findings_text = json.dumps({"findings": panel_findings})
    if telemetry_shape == "no-telemetry":
        engine = "claude"
        stdout = findings_text
    else:
        engine = "codex"
        stdout = _codex_event_stream(findings_text, action_items=1)
    ok, detail = engine_dispatch._open_review_run(
        run_dir, engine=engine, argv=[sys.executable, "-c", "pass"], cwd=repo_root,
        timeout=30, retry_timeout=30, prompt_path=order_path, view_path=view_path,
        view_meta=view_meta, fed_prompt=fed_prompt, order_id="panel-e2e-order",
        progress_path=os.path.join(run_dir, "progress.jsonl"), repo_root=repo_root,
        echo_nonce=echo_nonce, base_prompt=base_prompt,
    )
    assert ok, detail
    engine_dispatch._journal_append(run_dir, {
        "kind": "attempt-ended", "attempt": 1,
        "exit": 0, "timedOut": False, "refusal": None,
        "wallSeconds": 0.1, "stdoutBytes": len(stdout),
        "at": time.time(),
    })
    with open(os.path.join(run_dir, "attempt-1.stdout"), "wb") as fh:
        fh.write(stdout.encode("utf-8"))
    with open(os.path.join(run_dir, "attempt-1.stderr"), "wb") as fh:
        fh.write(b"")
    return run_dir


def _drive_one_phase_with_panel_dispatch_evidence(session_dir, tmp_path, gitdir,
                                                  panel_findings, head_diff_path,
                                                  telemetry_shape="dispatch-observed"):
    _assert_adapters_are_real()
    state = _state(session_dir)
    pend = state["pending"]
    phase = pend["phase"]
    roster, reason = round_adapters.roster_for(phase, state, state.get("config") or {})
    assert reason is None, (phase, reason)
    slots = _slots_of(roster)
    _write_dispatch_manifest(session_dir, pend, slots, _auditor_vendor_for(state))
    for seat, occurrence in slots:
        payload = _payload_for(session_dir, state, pend, seat, panel_findings, head_diff_path)
        if phase == round_driver.P_PANEL and seat == FINDING_SEAT and state["round"] == 1:
            _dispatch_observed_land(session_dir, state, pend, seat, payload, occurrence)
            order_path = round_records.order_prompt_path(
                session_dir, pend["round"], pend["phase"],
                round_records.storage_key(seat, occurrence), pend["attempt"])
            run_dir = _execution_run_dir(
                tmp_path, order_path, panel_findings, telemetry_shape=telemetry_shape)
            out = round_driver.cmd_record_result(
                session_dir, seat, occurrence=occurrence, evidence_run_dir=run_dir)
        else:
            _land(session_dir, state, pend, seat, payload, occurrence=occurrence)
            out = _record(session_dir, seat, occurrence=occurrence)
        assert out["ok"], (phase, seat, occurrence, out)
    if phase == round_driver.P_PANEL and telemetry_shape != "no-telemetry":
        # The runner record names the seat's real vendor (codex), so the harness owes
        # the control probe a real codex seat would have landed before advance.
        probe = {"engine": "codex", "outcome": "ok", "engaged": True, "detectedPlant": True,
                 "evidence": {"probe": "seat_canary"}}
        round_records.atomic_write_json(
            round_records.canary_path(session_dir, pend["round"], "codex", pend["attempt"]),
            probe)
    out = round_driver.cmd_advance(session_dir, git=_fake_git(gitdir))
    return phase, out


def _drive_to_terminal_with_panel_dispatch_evidence(session_dir, tmp_path, gitdir,
                                                      panel_findings, head_diff_path,
                                                      max_steps=24,
                                                      telemetry_shape="dispatch-observed"):
    folded = []
    for _ in range(max_steps):
        if _state(session_dir).get("terminal"):
            return folded
        before = _state(session_dir)["pending"]["phase"]
        phase, out = _drive_one_phase_with_panel_dispatch_evidence(
            session_dir, tmp_path, gitdir, panel_findings, head_diff_path,
            telemetry_shape=telemetry_shape)
        assert out["ok"], (phase, out)
        assert out["folded"]["phase"] == phase, out
        assert _state(session_dir)["step"] != before, (phase, _state(session_dir)["step"])
        folded.append(phase)
    raise AssertionError("did not reach a terminal in %d steps: %s" % (max_steps, folded))


def test_real_loop_refuses_dispatch_observed_without_cited_head_until_loop_records_head(
        tmp_path):
    """Seam between dispatch-observed telemetry and cited-head binding on the writer.

    The telemetry half is proven here: before certification the journal row's execution evidence
    shows read engaged, at least one tool call, and source codex-events. The head half waits for
    C13's producer — when the loop records the cited head on journal rows, this test flips to a
    certifying assertion under R28's classification.

    A review that raised findings is ``test_real_loop_with_finding_refuses_disposition_without_receipt_until_loop_records_dispositions``.
    """
    seat_map = {
        "seats": {
            dim: {"vendor": "codex", "model": "gpt-5.6-sol", "engine": "codex"}
            for dim in round_driver.DIMENSIONS
        }
    }
    session_dir, gitdir, head_path = _bootstrap(
        tmp_path,
        name="writer-e2e",
        seatMap=seat_map,
        vendors=["codex"],
        baseGuard=round_certification.BASE_GUARD_CHECKED,
    )
    folded = _drive_to_terminal_with_panel_dispatch_evidence(
        session_dir, tmp_path, gitdir, [], head_path)
    assert round_driver.P_PANEL in folded
    state = _state(session_dir)
    assert state["terminal"] == "converged", state.get("certification")
    journal = round_driver.read_journal(session_dir)
    recorded = [row for row in journal
                if row.get("outcome") == "recorded"
                and row.get("seat") == FINDING_SEAT
                and row.get("phase") == round_driver.P_PANEL
                and row.get("provenance") == round_records.PROVENANCE_DISPATCH_OBSERVED]
    assert recorded, journal
    evidence = recorded[0].get("executionEvidence")
    assert isinstance(evidence, dict)
    assert evidence.get("runnerNonce")
    observation = evidence["observation"]
    assert observation["read"] == "engaged"
    assert isinstance(observation["toolCalls"], int)
    assert observation["toolCalls"] >= 1
    assert observation["source"] == "codex-events"
    ctx, load_refusal = round_certification._load_context(session_dir)
    assert load_refusal is None, load_refusal
    certified_head = round_certification._certified_head_sha(ctx)
    assert isinstance(certified_head, str) and certified_head
    receipt, refusal = round_certification.certify(session_dir)
    assert receipt is None
    assert refusal is not None
    assert refusal["class"] == "unrun-review"
    assert (
        refusal["bindingFailure"]
        == round_certification.BINDING_FAILURE_EXECUTION_EVIDENCE_HEAD_UNBOUND
    )
    assert refusal["artifact"] == FINDING_SEAT


def test_real_loop_refuses_when_certified_head_unresolvable(tmp_path):
    """Proves a session with no resolvable certified head does not certify."""
    seat_map = {
        "seats": {
            dim: {"vendor": "codex", "model": "gpt-5.6-sol", "engine": "codex"}
            for dim in round_driver.DIMENSIONS
        }
    }
    session_dir, gitdir, head_path = _bootstrap(
        tmp_path,
        name="writer-e2e-no-meta-head",
        head_sha=None,
        seatMap=seat_map,
        vendors=["codex"],
        baseGuard=round_certification.BASE_GUARD_CHECKED,
    )
    _drive_to_terminal_with_panel_dispatch_evidence(
        session_dir, tmp_path, gitdir, [], head_path)
    receipt, refusal = round_certification.certify(session_dir)
    assert receipt is None
    assert refusal is not None
    assert refusal["class"] == "unrun-review"
    assert (
        refusal["bindingFailure"]
        == round_certification.BINDING_FAILURE_CERTIFIED_HEAD_UNRESOLVABLE
    )
    assert refusal["artifact"] == round_certification.META_FILE


def test_real_loop_refuses_dispatch_observed_seat_without_runner_tool_calls(tmp_path):
    """Proves the engagement gate bites on a real loop, not only on a fixture."""
    seat_map = {
        "seats": {
            dim: {"vendor": "codex", "model": "gpt-5.6-sol", "engine": "codex"}
            for dim in round_driver.DIMENSIONS
        }
    }
    session_dir, gitdir, head_path = _bootstrap(
        tmp_path,
        name="writer-e2e-no-telemetry",
        seatMap=seat_map,
        vendors=["codex"],
        baseGuard=round_certification.BASE_GUARD_CHECKED,
    )
    findings = [_blocking_finding("missing bounds guard", 2)]
    folded = _drive_to_terminal_with_panel_dispatch_evidence(
        session_dir, tmp_path, gitdir, findings, head_path,
        telemetry_shape="no-telemetry")
    assert round_driver.P_PANEL in folded
    state = _state(session_dir)
    assert state["terminal"] == "converged", state.get("certification")
    receipt, refusal = round_certification.certify(session_dir)
    assert receipt is None
    assert refusal is not None
    assert refusal["class"] == "unrun-review"
    assert refusal["bindingFailure"] == "execution-evidence-no-runner-action"


def test_real_loop_with_finding_refuses_disposition_without_receipt_until_loop_records_dispositions(
        tmp_path):
    """Seam between this child (the writer's disposition-without-receipt check) and C13.

    C13 lands the loop's disposition recording at ``round_driver.py`` :2349, :2720, and :3318,
    all routed through ``_set_findings``. When that producer lands, this test flips to a certifying
    assertion in C13 under R28's first clause (the behavior is fixed and the test is kept). This
    is not a statement that refusing is desirable — only that refusing is what the code correctly
    does while no producer exists.
    """
    seat_map = {
        "seats": {
            dim: {"vendor": "codex", "model": "gpt-5.6-sol", "engine": "codex"}
            for dim in round_driver.DIMENSIONS
        }
    }
    session_dir, gitdir, head_path = _bootstrap(
        tmp_path,
        name="writer-e2e-disposition-seam",
        seatMap=seat_map,
        vendors=["codex"],
        baseGuard=round_certification.BASE_GUARD_CHECKED,
    )
    finding = _blocking_finding("missing bounds guard", 2)
    folded = _drive_to_terminal_with_panel_dispatch_evidence(
        session_dir, tmp_path, gitdir, [finding], head_path)
    assert round_driver.P_PANEL in folded
    state = _state(session_dir)
    assert state["terminal"] == "converged", state.get("certification")
    receipt, refusal = round_certification.certify(session_dir)
    assert receipt is None
    assert refusal is not None
    assert refusal["class"] == "disposition-without-receipt"
    assert refusal["artifact"] == finding["title"]
    assert refusal["detail"] == "finding has no disposition recorded"


def _git(cwd, *args, check=True):
    return subprocess.run(
        ["git", "-C", cwd, *args], capture_output=True, text=True, check=check,
    )


def _init_repo(path):
    os.makedirs(path, exist_ok=True)
    _git(path, "init", "-q")
    readme = os.path.join(path, "README.md")
    with open(readme, "w", encoding="utf-8") as fh:
        fh.write("hello\n")
    _git(path, "add", "README.md")
    _git(path, "-c", "user.email=t@t.local", "-c", "user.name=t", "commit", "-qm", "init")
    return path


def _linked_worktree(tmp_path):
    main = str(tmp_path / "main")
    _init_repo(main)
    wt = str(tmp_path / "wt")
    _git(main, "worktree", "add", "-q", wt)
    return wt, main


def _write_ok_stdout():
    body = json.dumps({
        "ok": True, "signal": "ok",
        "evidence": {"testFailed": False, "testPassed": True},
    })
    return "Receipt prose.\n" + engine_adapter.WRITE_REPORT_SENTINEL + "\n" + body


def _write_execution_run_dir(tmp_path, order_path, echo_nonce="nonce-fixer-e2e"):
    """Build a write run directory for fixer dispatch-evidence tests."""
    run_dir = str(tmp_path / "fixer-write-evidence-run")
    journal_root = str(tmp_path / "fixer-dispatch-journal-root")
    os.makedirs(journal_root, exist_ok=True)
    os.environ[engine_dispatch.JOURNAL_ROOT_ENV] = journal_root
    wt, _main = _linked_worktree(tmp_path / "fixer-git")
    wt_real = os.path.realpath(wt)
    baseline = engine_dispatch._worktree_baseline(wt_real)
    engine_dispatch._acquire_worktree_lease(wt_real, run_dir)
    ok, detail = engine_dispatch._open_write_run(
        run_dir, engine="codex", argv=[sys.executable, "-c", "pass"], cwd=wt_real,
        timeout=engine_dispatch.RETRY_MIN_TIMEOUT,
        retry_timeout=engine_dispatch.RETRY_MIN_TIMEOUT,
        prompt_path=order_path, order_id="fixer-e2e-order", base_sha="abc",
        worktree_baseline=baseline, progress_path=os.path.join(run_dir, "progress.jsonl"),
    )
    assert ok, detail
    stdout = _write_ok_stdout()
    records, _ = engine_dispatch._journal_read(run_dir)
    path = engine_dispatch._journal_path(run_dir)
    with open(path, "w", encoding="utf-8") as fh:
        for rec in records:
            if rec.get("kind") == "run-opened":
                rec["echoNonce"] = echo_nonce
            fh.write(json.dumps(rec, separators=(",", ":")) + "\n")
    engine_dispatch._journal_append(run_dir, {
        "kind": "attempt-started", "attempt": 1, "childPid": 1, "at": time.time(),
    })
    with open(os.path.join(run_dir, "attempt-1.stdout"), "w", encoding="utf-8") as fh:
        fh.write(stdout)
    with open(os.path.join(run_dir, "attempt-1.stderr"), "w", encoding="utf-8") as fh:
        fh.write("")
    engine_dispatch._journal_append(run_dir, {
        "kind": "attempt-ended", "attempt": 1,
        "exit": 0, "timedOut": False, "refusal": None,
        "wallSeconds": 1.0, "stdoutBytes": len(stdout),
        "at": time.time(),
    })
    return run_dir


def _fixer_envelope_for_write_run(record, *, order_sha=None):
    payload = {"fixes": [{"file": FIXED_FILE, "description": "applied fix"}]}
    return {
        "orderSha256": order_sha if order_sha is not None else record["orderPromptSha256"],
        "payload": payload,
    }


def test_assemble_dispatch_evidence_write_run_fixer_envelope(tmp_path):
    order_path = str(tmp_path / "fixer-order.txt")
    with open(order_path, "w", encoding="utf-8") as fh:
        fh.write("Fix the bug.\n")
    run_dir = _write_execution_run_dir(tmp_path, order_path)
    record, err = engine_dispatch.run_execution_record(run_dir)
    assert err is None, err
    envelope = _fixer_envelope_for_write_run(record)
    assembled, refusal, extra = round_driver._assemble_dispatch_evidence(
        str(tmp_path / "session"), envelope, run_dir)
    assert refusal is None, extra
    assert assembled is not None
    assert assembled["executionEvidence"]["resultKind"] == session_contract.WRITE_RESULT_KIND
    assert assembled["envelopeSha256"] == round_records.envelope_sha256(
        envelope["payload"], assembled["executionEvidence"])


def test_assemble_dispatch_evidence_write_run_order_mismatch_refuses(tmp_path):
    order_path = str(tmp_path / "fixer-order-mismatch.txt")
    with open(order_path, "w", encoding="utf-8") as fh:
        fh.write("Fix the bug.\n")
    run_dir = _write_execution_run_dir(tmp_path, order_path)
    record, err = engine_dispatch.run_execution_record(run_dir)
    assert err is None, err
    envelope = _fixer_envelope_for_write_run(record, order_sha="0" * 64)
    assembled, refusal, extra = round_driver._assemble_dispatch_evidence(
        str(tmp_path / "session"), envelope, run_dir)
    assert assembled is None
    assert refusal == "evidence-order-mismatch"


def test_assemble_dispatch_evidence_write_run_binding_incomplete_refuses(tmp_path):
    order_path = str(tmp_path / "fixer-order-incomplete.txt")
    with open(order_path, "w", encoding="utf-8") as fh:
        fh.write("Fix the bug.\n")
    run_dir = _write_execution_run_dir(tmp_path, order_path)
    with open(os.path.join(run_dir, "attempt-1.stdout"), "w", encoding="utf-8") as fh:
        fh.write("not a write report\n")
    record, err = engine_dispatch.run_execution_record(run_dir)
    assert err is None, err
    assert "resultDigest" not in record
    envelope = _fixer_envelope_for_write_run(record)
    assembled, refusal, extra = round_driver._assemble_dispatch_evidence(
        str(tmp_path / "session"), envelope, run_dir)
    assert assembled is None
    assert refusal == "evidence-run-dir-unreadable"
    assert extra.get("detail") == "result-binding-incomplete"


def test_assemble_dispatch_evidence_kind_not_in_payload_refuses(tmp_path):
    order_path = str(tmp_path / "fixer-order-unknown-kind.txt")
    with open(order_path, "w", encoding="utf-8") as fh:
        fh.write("Fix the bug.\n")
    run_dir = _write_execution_run_dir(tmp_path, order_path)
    record, err = engine_dispatch.run_execution_record(run_dir)
    assert err is None, err
    real_record = engine_dispatch.run_execution_record

    def _patched(run_dir_arg):
        out, error = real_record(run_dir_arg)
        if out is not None:
            out = dict(out)
            out["resultKind"] = "unknown-kind"
        return out, error

    engine_dispatch.run_execution_record = _patched
    try:
        envelope = _fixer_envelope_for_write_run(record)
        assembled, refusal, extra = round_driver._assemble_dispatch_evidence(
            str(tmp_path / "session"), envelope, run_dir)
    finally:
        engine_dispatch.run_execution_record = real_record
    assert assembled is None
    assert refusal == "evidence-result-mismatch"
    assert extra.get("resultKind") == "unknown-kind"


def test_assemble_dispatch_evidence_review_kind_absent_from_payload_refuses(tmp_path):
    order_path = str(tmp_path / "review-order.txt")
    with open(order_path, "w", encoding="utf-8") as fh:
        fh.write("Review this.\n")
    run_dir = _execution_run_dir(tmp_path, order_path, [])
    record, err = engine_dispatch.run_execution_record(run_dir)
    assert err is None, err
    envelope = {
        "orderSha256": record["orderPromptSha256"],
        "payload": {"fixes": []},
    }
    assembled, refusal, extra = round_driver._assemble_dispatch_evidence(
        str(tmp_path / "session"), envelope, run_dir)
    assert assembled is None
    assert refusal == "evidence-result-mismatch"
    assert extra.get("resultKind") == "findings"
