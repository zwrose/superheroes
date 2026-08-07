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
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

# PLAIN imports, not importlib side-loads: the driver imports `round_adapters` at CALL time through
# `sys.modules`, so the module objects this test asserts about must be the very ones the driver
# reaches. A side-loaded copy would let a stub sit in `sys.modules` unnoticed.
import round_adapters  # noqa: E402
import round_driver  # noqa: E402
import round_records  # noqa: E402

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
            return "a" * 40
        if args[:3] == ("rev-parse", "--abbrev-ref", "HEAD"):
            return "feature/x"
        if args[0] == "rev-parse" and "--verify" in args:
            return "b" * 40
        if args[:2] == ("remote", "get-url"):
            return "github.com/o/r"
        return None
    return run


def _anchor_hashes(session_dir, state, pend, seat):
    """The emission-time anchor an envelope must echo (`round_records._anchor_check`)."""
    anchor = round_driver._orders_anchor(state, session_dir, pend["round"], pend["phase"],
                                         pend["attempt"])
    if anchor is None:
        return round_records.NOT_EMITTED, round_records.NOT_EMITTED
    return anchor["manifestSha256"], (anchor.get("orders") or {}).get(
        seat, round_records.NOT_EMITTED)


def _land(session_dir, state, pend, seat, payload, occurrence=0):
    """Write ONE seat's `seat-result/1` envelope into the LANDING area (what the host does)."""
    manifest_sha, order_sha = _anchor_hashes(session_dir, state, pend, seat)
    envelope = {
        "schema": round_records.SEAT_RESULT_SCHEMA,
        "session": _session_id(session_dir),
        "round": pend["round"],
        "phase": pend["phase"],
        "seat": seat,
        "attempt": pend["attempt"],
        "vendor": "claude",
        "model": "sonnet-5",
        "dispatchRef": "dispatch-1",
        "orderSha256": order_sha,
        "manifestSha256": manifest_sha,
        "recordedAt": "2026-08-07T00:00:00",
        "payloadSha256": round_records.payload_sha256(payload),
        "payload": payload,
    }
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


def _bootstrap(tmp_path, name="s", **cfg_over):
    session_dir = str(tmp_path / name)
    os.makedirs(session_dir, exist_ok=True)
    gitdir = str(tmp_path / (name + "-gitdir"))
    os.makedirs(gitdir, exist_ok=True)
    head_diff_path = str(tmp_path / (name + "-head.diff"))
    with open(head_diff_path, "w", encoding="utf-8") as fh:
        fh.write(HEAD_DIFF)
    out = round_driver.cmd_next(session_dir, _cfg(**cfg_over))
    assert out["ok"], out
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
    driver, and its functions must come from `round_adapters` itself (a per-function patch leaves
    the module identity intact but re-hides the seam)."""
    _assert_adapters_are_real()
    assert round_adapters.__name__ == "round_adapters"
    assert round_adapters.missing_policy.__module__ == "round_adapters"
    assert round_adapters.payload_fault.__module__ == "round_adapters"
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


def test_two_audit_targets_sharing_one_id_are_both_recorded_and_both_folded(tmp_path):
    """`finding_identity` is LINE-LESS, so two findings with the same title at DIFFERENT lines in
    one file compile as DISTINCT findings and produce TWO audit targets with ONE id. Keyed by seat
    alone the second target's record collides with the first, and only ONE ruling reaches the fold.

    The discriminator is the `ambiguous` disclosure. `audits.apply_audit_results` keys results by
    finding id, so it can only SEE the ambiguity when BOTH results arrive; with one arriving it
    matches that single ruling to BOTH targets and discharges a target nobody audited. So:

      - both records folded → `ambiguous: [id]`, both targets not-discharged (fail closed);
      - one record folded   → no ambiguity, both targets DISCHARGED off one audit.

    The second is a false certification, which is why the slot — not the seat — is the identity.
    (Residual, reported not fixed: the audits FOLD still cannot tell two same-id targets apart, so
    it fails them closed rather than discharging each on its own ruling. That is `audits.py`'s
    line-less identity model, downstream of this seam and outside this change.)"""
    session_dir, gitdir, head_path = _bootstrap(tmp_path, name="collide")
    findings = [_blocking_finding("unchecked index", 2), _blocking_finding("unchecked index", 3)]
    _drive_to_phase(session_dir, gitdir, findings, head_path, round_driver.P_AUDITS)

    state = _state(session_dir)
    targets = state["_auditTargets"]
    assert len(targets) == 2, targets
    assert targets[0]["id"] == targets[1]["id"], targets
    tid = targets[0]["id"]

    roster, reason = round_adapters.roster_for(round_driver.P_AUDITS, state,
                                               state.get("config") or {})
    assert reason is None and roster == [tid, tid], roster

    # each occurrence lands and records into its OWN durable slot
    pend = state["pending"]
    _write_dispatch_manifest(session_dir, pend, _slots_of(roster), _auditor_vendor_for(state))
    store_paths = []
    for occurrence in (0, 1):
        payload = {"id": tid, "ruling": "discharged", "auditorVendor": "claude",
                   "reason": "re-read hunk #%d; the cited defect is gone" % occurrence}
        _land(session_dir, state, pend, tid, payload, occurrence=occurrence)
        out = _record(session_dir, tid, occurrence=occurrence)
        assert out["ok"], (occurrence, out)
        store_paths.append(out["storePath"])
    assert store_paths[0] != store_paths[1], store_paths

    out = round_driver.cmd_advance(session_dir, git=_fake_git(gitdir))
    assert out["ok"] is True, out
    assert out["folded"]["phase"] == round_driver.P_AUDITS

    # BOTH rulings reached the fold — neither slot's record was dropped or overwritten
    state_after = _state(session_dir)
    audits_round = state_after["auditRounds"][-1]
    assert [a["identity"] for a in audits_round["outcomes"]] == [tid, tid], audits_round
    # the ambiguity is VISIBLE only because two results carrying that id arrived
    assert state_after["_auditOutcome"]["ambiguous"] == [tid], state_after["_auditOutcome"]
    assert [a["ruling"] for a in audits_round["outcomes"]] == \
        ["not-discharged", "not-discharged"], audits_round
    # …and nothing was certified off a single audit: both targets stay open
    assert state_after["_auditOutcome"]["discharged"] == [], state_after["_auditOutcome"]
    assert state_after["_auditOutcome"]["notDischarged"] == [tid, tid], \
        state_after["_auditOutcome"]


def test_a_missing_second_occurrence_is_named_by_slot_not_by_seat(tmp_path):
    """A/B against the test above: with only occurrence 0 recorded, `advance` refuses
    `incomplete-roster` and NAMES the absent slot `<seat>#1` — a bare `<seat>` would read as "the
    whole target is missing" while its twin is on disk."""
    session_dir, gitdir, head_path = _bootstrap(tmp_path, name="collide-short")
    findings = [_blocking_finding("unchecked index", 2), _blocking_finding("unchecked index", 3)]
    _drive_to_phase(session_dir, gitdir, findings, head_path, round_driver.P_AUDITS)

    state = _state(session_dir)
    tid = state["_auditTargets"][0]["id"]
    pend = state["pending"]
    _write_dispatch_manifest(session_dir, pend, [(tid, 0), (tid, 1)], _auditor_vendor_for(state))
    _land(session_dir, state, pend, tid,
          {"id": tid, "ruling": "discharged", "reason": "re-read the hunk; the defect is gone"})
    assert _record(session_dir, tid)["ok"] is True

    out = round_driver.cmd_advance(session_dir, git=_fake_git(gitdir))
    assert out["ok"] is False and out["reason"] == "incomplete-roster", out
    assert out["seats"] == ["%s#1" % tid], out


def test_record_missing_addresses_the_second_occurrence(tmp_path):
    """`record-missing` owes the same slot addressing: a second target sharing an id must be
    recordable as absent WITHOUT claiming its twin is absent too."""
    session_dir, gitdir, head_path = _bootstrap(tmp_path, name="collide-missing")
    findings = [_blocking_finding("unchecked index", 2), _blocking_finding("unchecked index", 3)]
    _drive_to_phase(session_dir, gitdir, findings, head_path, round_driver.P_AUDITS)

    state = _state(session_dir)
    tid = state["_auditTargets"][0]["id"]
    pend = state["pending"]
    _land(session_dir, state, pend, tid,
          {"id": tid, "ruling": "discharged", "reason": "re-read the hunk; the defect is gone"})
    assert _record(session_dir, tid)["ok"] is True
    out = round_driver.cmd_record_missing(session_dir, tid, pend["attempt"], "forfeit",
                                          occurrence=1)
    assert out["ok"] is True, out

    stored, err = round_records.read_json(out["storePath"])
    assert err is None and stored["occurrence"] == 1, (err, stored)
    # the two slots are distinct files: the missing record did not overwrite the recorded ruling
    other = round_records.store_path(session_dir, pend["round"], pend["phase"],
                                     round_records.storage_key(tid, 0), pend["attempt"])
    kept, err = round_records.read_json(other)
    assert err is None and kept["schema"] == round_records.SEAT_RESULT_SCHEMA, (err, kept)


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
