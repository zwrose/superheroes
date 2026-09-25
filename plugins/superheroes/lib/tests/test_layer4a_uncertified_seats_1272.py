"""#1272 layer 4a: host-channel seats named out of certified panel, not refused."""
import importlib.util
import json
import os
import sys

import pytest
import record_paths
import session_contract as SC

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

from round_certification_fixtures import (
    DEFAULT_FINDINGS_RESULT_SHA,
    DEFAULT_PANEL_PAYLOAD_SHA,
    write_session,
)

import round_certification as RC
import round_phases as RP

from test_round_certification import (
    _binding_fields,
    _dispatch_journal_with_binding,
    _hand_landed_binding_journal_row,
    _minimal_orders_manifest,
    _orders_emitted_journal_row,
    _write_orders_manifest,
    write_certifiable_session,
)

HEAD = "a" * 40


def _load_round_driver():
    spec = importlib.util.spec_from_file_location(
        "round_driver", os.path.join(_LIB, "round_driver.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _dispatch_observed_no_telemetry_row(
    seat,
    phase,
    *,
    rnd=1,
    attempt=0,
    occurrence=0,
    payload_sha=DEFAULT_PANEL_PAYLOAD_SHA,
):
    return {
        "cmd": "record-result",
        "outcome": "recorded",
        "phase": phase,
        "round": rnd,
        "attempt": attempt,
        "seat": seat,
        "occurrence": occurrence,
        "provenance": RC.PROVENANCE_DISPATCH_OBSERVED,
        "payloadSha256": payload_sha,
        "recordIdentity": {
            "phase": phase,
            "seat": seat,
            "occurrence": occurrence,
            "attempt": attempt,
        },
    }


def _manifest_seat_entry(seat, channel, vendor, *, occurrence=0):
    skey = record_paths.storage_key(seat, occurrence)
    return skey, {
        "storeKey": skey,
        "seat": seat,
        "occurrence": occurrence,
        "vendor": vendor,
        "model": "sonnet",
        "engine": vendor,
        "channel": channel,
        "resultContract": "seat-result/2",
        "orderSha256": "a" * 64,
        "orderPath": "/dev/null",
        "envelopeStubPath": "/dev/null",
    }


def _qualifying_dispatch_row(seat, phase):
    row = _dispatch_journal_with_binding(seat=seat)
    row["phase"] = phase
    row["seat"] = seat
    row["recordIdentity"]["phase"] = phase
    row["recordIdentity"]["seat"] = seat
    return row


def _multi_phase_session(tmp_path, phase_specs, *, rnd=1, attempt=0):
    """Build a session with one orders-manifest per phase in ``phase_specs``."""
    journal_lines = []
    all_envelopes = []
    manifests = []
    for phase, seat_configs in phase_specs.items():
        manifest_seats = {}
        for cfg in seat_configs:
            journal_lines.append(cfg["row"])
            skey, entry = _manifest_seat_entry(
                cfg["seat"], cfg["channel"], cfg["vendor"])
            manifest_seats[skey] = entry
            all_envelopes.append(cfg.get("envelope", {
                "seat": cfg["seat"],
                "phase": phase,
                "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA,
            }))
        manifest = {
            "schema": "orders-manifest/1",
            "session": "test-session-001",
            "round": rnd,
            "phase": phase,
            "attempt": attempt,
            "orders": "not-emitted",
            "seats": manifest_seats,
        }
        manifest_sha = SC.sha256_text(SC.canonical(manifest))
        journal_lines.append(_orders_emitted_journal_row(
            manifest_sha, phase=phase, rnd=rnd, attempt=attempt))
        manifests.append(manifest)
    session_dir = write_session(
        tmp_path, journal_lines=journal_lines, envelopes=all_envelopes)
    for manifest in manifests:
        _write_orders_manifest(session_dir, manifest)
    return session_dir


def _session_with_manifest(
    tmp_path,
    *,
    seat,
    phase,
    channel,
    vendor,
    journal_lines,
    envelopes,
    manifest_phase=None,
    attempt=0,
    rnd=1,
):
    manifest_phase = manifest_phase if manifest_phase is not None else phase
    skey, entry = _manifest_seat_entry(seat, channel, vendor)
    manifest = {
        "schema": "orders-manifest/1",
        "session": "test-session-001",
        "round": rnd,
        "phase": manifest_phase,
        "attempt": attempt,
        "orders": "not-emitted",
        "seats": {skey: entry},
    }
    manifest_sha = SC.sha256_text(SC.canonical(manifest))
    lines = list(journal_lines)
    lines.append(_orders_emitted_journal_row(
        manifest_sha, phase=manifest_phase, rnd=rnd, attempt=attempt))
    session_dir = write_session(tmp_path, journal_lines=lines, envelopes=envelopes)
    _write_orders_manifest(session_dir, manifest)
    return session_dir, manifest


def _panel_host_uncertified_session(tmp_path, host_seat="code-reviewer", engine_seat="security-reviewer"):
    """Panel with one host seat (no telemetry) and one engine seat (with telemetry)."""
    host_row = _dispatch_observed_no_telemetry_row(host_seat, RP.P_PANEL)
    engine_row = _dispatch_journal_with_binding(seat=engine_seat)
    engine_row["phase"] = RP.P_PANEL
    engine_row["seat"] = engine_seat
    engine_row["recordIdentity"]["phase"] = RP.P_PANEL
    engine_row["recordIdentity"]["seat"] = engine_seat
    skey_host, host_entry = _manifest_seat_entry(host_seat, "file", "claude")
    skey_engine, engine_entry = _manifest_seat_entry(engine_seat, "stdout", "codex")
    manifest = {
        "schema": "orders-manifest/1",
        "session": "test-session-001",
        "round": 1,
        "phase": RP.P_PANEL,
        "attempt": 0,
        "orders": "not-emitted",
        "seats": {skey_host: host_entry, skey_engine: engine_entry},
    }
    manifest_sha = SC.sha256_text(SC.canonical(manifest))
    envelopes = [
        {"seat": host_seat, "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA},
        {"seat": engine_seat, "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA},
    ]
    session_dir = write_session(
        tmp_path,
        journal_lines=[
            host_row,
            engine_row,
            _orders_emitted_journal_row(manifest_sha),
        ],
        envelopes=envelopes,
    )
    _write_orders_manifest(session_dir, manifest)
    return session_dir


# --- edge 1: host panel seat without telemetry → uncertified, no per-seat refusal --------


def test_l4a_edge1_host_panel_refuses_unrun_review(tmp_path):
    """R28 (owner ruling 1=b): host panel seat refuses unrun-review."""
    session_dir = _panel_host_uncertified_session(tmp_path)
    ctx, err = RC._load_context(session_dir)
    assert err is None
    refusal = RC.check_unrun_review(ctx)
    assert refusal is not None
    assert refusal["class"] == "unrun-review"
    assert refusal["artifact"] == "code-reviewer"
    assert refusal["bindingFailure"] == "execution-evidence-absent"


def test_l4a_certify_refuses_host_panel_seat(tmp_path):
    """R28: certification refuses when a host-channel panel seat lacks runner evidence."""
    host_seat = "code-reviewer"
    engine_seat = "security-reviewer"
    host_row = _dispatch_observed_no_telemetry_row(host_seat, RP.P_PANEL)
    host_row["headSha"] = HEAD
    host_row["citedHead"] = HEAD
    engine_row = _dispatch_journal_with_binding(seat=engine_seat, head_sha=HEAD)
    engine_row["phase"] = RP.P_PANEL
    engine_row["seat"] = engine_seat
    engine_row["recordIdentity"]["phase"] = RP.P_PANEL
    engine_row["recordIdentity"]["seat"] = engine_seat
    skey_host, host_entry = _manifest_seat_entry(host_seat, SC.CHANNEL_FILE, "claude")
    skey_engine, engine_entry = _manifest_seat_entry(engine_seat, SC.CHANNEL_STDOUT, "codex")
    manifest = {
        "schema": "orders-manifest/1",
        "session": "test-session-001",
        "round": 1,
        "phase": RP.P_PANEL,
        "attempt": 0,
        "orders": "not-emitted",
        "seats": {skey_host: host_entry, skey_engine: engine_entry},
    }
    manifest_sha = SC.sha256_text(SC.canonical(manifest))
    session_dir = write_certifiable_session(
        tmp_path,
        journal_lines=[
            host_row,
            engine_row,
            _orders_emitted_journal_row(manifest_sha),
        ],
        envelopes=[
            {"seat": host_seat, "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA},
            {"seat": engine_seat, "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA},
        ],
        state={
            "config": {
                "fixerVendor": "cursor",
                "baseGuard": RC.BASE_GUARD_CHECKED,
                "headSha": HEAD,
            },
            "seatMapReceipts": [{
                "round": "1",
                "map": {
                    "seats": {
                        host_seat: {"vendor": "claude", "model": "sonnet"},
                        engine_seat: {"vendor": "codex", "model": "gpt"},
                    },
                },
            }],
        },
    )
    _write_orders_manifest(session_dir, manifest)
    receipt, refusal = RC.certify(session_dir)
    assert receipt is None
    assert refusal is not None
    assert refusal["class"] == "unrun-review"
    assert refusal["artifact"] == host_seat
    assert refusal["bindingFailure"] == "execution-evidence-absent"


# --- provenance census: writer receipt omits retired host-seat exclusion labels ----------


def _derived_seat_map_row_field_labels(derived_labels):
    prefix = "seatMap.seats.*."
    return {
        label[len(prefix):]
        for label in derived_labels
        if label.startswith(prefix)
    }


def test_l4a_seat_map_injected_keys_provenance_census(tmp_path):
    session_dir = _panel_host_uncertified_session(tmp_path)
    ctx, err = RC._load_context(session_dir)
    assert err is None
    state = ctx["state"]
    state["seatMapReceipts"] = [{
        "round": "1",
        "map": {
            "seats": {
                "code-reviewer": {"vendor": "claude", "model": "sonnet"},
                "security-reviewer": {"vendor": "codex", "model": "gpt"},
            },
        },
    }]
    source_seats = {}
    for entry in state["seatMapReceipts"]:
        seats = (entry.get("map") or {}).get("seats") or {}
        source_seats.update(seats)
    receipt, refusal = RC._build_receipt(ctx, "certified", None)
    assert refusal is None
    derived = receipt["provenanceLabels"]["derived"]
    assert "seatMap.seats.*.certifiedPanel" not in derived
    assert "uncertifiedSeats" not in receipt.get("disclosures", {})


# --- edge 2: sole host on non-panel phase with no panel row → floor refuses ---------------


@pytest.mark.parametrize("phase", (
    RP.P_VERIFIERS,
    RP.P_GAPSWEEP,
    RP.P_SCOPED,
    RP.P_SYNTHESIS,
))
def test_l4a_edge2_host_non_panel_phase_uncertified_named(tmp_path, phase):
    seat = "reviewer-seat"
    row = _dispatch_observed_no_telemetry_row(seat, phase)
    session_dir, _ = _session_with_manifest(
        tmp_path,
        seat=seat,
        phase=phase,
        channel="file",
        vendor="claude",
        journal_lines=[row],
        envelopes=[{"seat": seat, "phase": phase, "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}],
    )
    ctx, err = RC._load_context(session_dir)
    assert err is None
    refusal = RC.check_unrun_review(ctx)
    assert refusal is not None
    assert refusal["class"] == "unrun-review"
    assert refusal["artifact"] == seat
    assert refusal["bindingFailure"] == "execution-evidence-absent"


# --- edge 3: host on audits/fixer → refuses as today -------------------------------------


@pytest.mark.parametrize("phase", (RP.P_AUDITS, RP.P_FIXER))
def test_l4a_edge3_host_audits_fixer_refuses(tmp_path, phase):
    seat = "audit-seat" if phase == RP.P_AUDITS else "fixer"
    row = _dispatch_observed_no_telemetry_row(seat, phase)
    session_dir, _ = _session_with_manifest(
        tmp_path,
        seat=seat,
        phase=phase,
        channel="file",
        vendor="claude",
        journal_lines=[row],
        envelopes=[{"seat": seat, "phase": phase, "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}],
    )
    ctx, err = RC._load_context(session_dir)
    assert err is None
    refusal = RC.check_unrun_review(ctx)
    assert refusal is not None
    assert refusal["class"] == "unrun-review"
    assert refusal["artifact"] == seat


# --- edge 4: engine seat without telemetry → refuses as today ----------------------------


def test_l4a_edge4_engine_stdout_without_telemetry_refuses(tmp_path):
    seat = "code-reviewer"
    row = _dispatch_observed_no_telemetry_row(seat, RP.P_PANEL)
    session_dir, _ = _session_with_manifest(
        tmp_path,
        seat=seat,
        phase=RP.P_PANEL,
        channel="stdout",
        vendor="codex",
        journal_lines=[row],
        envelopes=[{"seat": seat, "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}],
    )
    ctx, err = RC._load_context(session_dir)
    assert err is None
    refusal = RC.check_unrun_review(ctx)
    assert refusal is not None
    assert refusal["class"] == "unrun-review"
    assert refusal["artifact"] == seat


# --- edge 5: manifest without channel key → refuses as today -----------------------------


def test_l4a_edge5_manifest_missing_channel_refuses(tmp_path):
    seat = "code-reviewer"
    row = _dispatch_observed_no_telemetry_row(seat, RP.P_PANEL)
    skey, entry = _manifest_seat_entry(seat, "file", "claude")
    entry.pop("channel", None)
    manifest = {
        "schema": "orders-manifest/1",
        "session": "test-session-001",
        "round": 1,
        "phase": RP.P_PANEL,
        "attempt": 0,
        "orders": "not-emitted",
        "seats": {skey: entry},
    }
    manifest_sha = SC.sha256_text(SC.canonical(manifest))
    session_dir = write_session(
        tmp_path,
        journal_lines=[
            row,
            _orders_emitted_journal_row(manifest_sha),
        ],
        envelopes=[{"seat": seat, "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}],
    )
    _write_orders_manifest(session_dir, manifest)
    ctx, err = RC._load_context(session_dir)
    assert err is None
    refusal = RC.check_unrun_review(ctx)
    assert refusal is not None
    assert refusal["class"] == "unrun-review"
    assert refusal["artifact"] == seat


# --- edge 6: tampered manifest sha → refuses as today ------------------------------------


def test_l4a_edge6_tampered_manifest_sha_refuses(tmp_path):
    seat = "code-reviewer"
    row = _dispatch_observed_no_telemetry_row(seat, RP.P_PANEL)
    session_dir, manifest = _session_with_manifest(
        tmp_path,
        seat=seat,
        phase=RP.P_PANEL,
        channel="file",
        vendor="claude",
        journal_lines=[row],
        envelopes=[{"seat": seat, "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}],
    )
    manifest["seats"][record_paths.storage_key(seat, 0)]["vendor"] = "tampered"
    _write_orders_manifest(session_dir, manifest)
    ctx, err = RC._load_context(session_dir)
    assert err is None
    refusal = RC.check_unrun_review(ctx)
    assert refusal is not None
    assert refusal["class"] == "unrun-review"
    assert refusal["artifact"] == seat


# --- edge 7: missing manifest or seat → refuses as today ---------------------------------


def test_l4a_edge7_missing_manifest_refuses(tmp_path):
    seat = "code-reviewer"
    row = _dispatch_observed_no_telemetry_row(seat, RP.P_PANEL)
    session_dir = write_session(
        tmp_path,
        journal_lines=[
            row,
            _orders_emitted_journal_row("a" * 64),
        ],
        envelopes=[{"seat": seat, "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}],
    )
    ctx, err = RC._load_context(session_dir)
    assert err is None
    refusal = RC.check_unrun_review(ctx)
    assert refusal is not None
    assert refusal["class"] == "unrun-review"


def test_l4a_edge7_seat_missing_from_manifest_refuses(tmp_path):
    seat = "code-reviewer"
    row = _dispatch_observed_no_telemetry_row(seat, RP.P_PANEL)
    manifest = _minimal_orders_manifest()
    manifest_sha = SC.sha256_text(SC.canonical(manifest))
    session_dir = write_session(
        tmp_path,
        journal_lines=[row, _orders_emitted_journal_row(manifest_sha)],
        envelopes=[{"seat": seat, "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}],
    )
    _write_orders_manifest(session_dir, manifest)
    ctx, err = RC._load_context(session_dir)
    assert err is None
    refusal = RC.check_unrun_review(ctx)
    assert refusal is not None
    assert refusal["class"] == "unrun-review"
    assert refusal["artifact"] == seat


# --- exclusion-floor census: post-loop predicate over collected seats --------------------


@pytest.mark.parametrize("case_id,phase_specs,expect_refusal", (
    (
        "no_panel_verifiers",
        {RP.P_VERIFIERS: [{
            "seat": "verifier-seat",
            "channel": "file",
            "vendor": "claude",
            "row": _dispatch_observed_no_telemetry_row("verifier-seat", RP.P_VERIFIERS),
        }]},
        True,
    ),
    (
        "no_panel_gapsweep",
        {RP.P_GAPSWEEP: [{
            "seat": "gapsweep-seat",
            "channel": "file",
            "vendor": "claude",
            "row": _dispatch_observed_no_telemetry_row("gapsweep-seat", RP.P_GAPSWEEP),
        }]},
        True,
    ),
    (
        "no_panel_scoped",
        {RP.P_SCOPED: [{
            "seat": "scoped-seat",
            "channel": "file",
            "vendor": "claude",
            "row": _dispatch_observed_no_telemetry_row("scoped-seat", RP.P_SCOPED),
        }]},
        True,
    ),
    (
        "no_panel_synthesis",
        {RP.P_SYNTHESIS: [{
            "seat": "synthesis-seat",
            "channel": "file",
            "vendor": "claude",
            "row": _dispatch_observed_no_telemetry_row("synthesis-seat", RP.P_SYNTHESIS),
        }]},
        True,
    ),
    (
        "all_panel_excluded_plus_qualified_audit",
        {
            RP.P_PANEL: [{
                "seat": "code-reviewer",
                "channel": "file",
                "vendor": "claude",
                "row": _dispatch_observed_no_telemetry_row("code-reviewer", RP.P_PANEL),
            }],
            RP.P_AUDITS: [{
                "seat": "audit-seat",
                "channel": "stdout",
                "vendor": "codex",
                "row": _qualifying_dispatch_row("audit-seat", RP.P_AUDITS),
            }],
        },
        True,
    ),
    (
        "all_panel_excluded_plus_excluded_nonpanel",
        {
            RP.P_PANEL: [{
                "seat": "code-reviewer",
                "channel": "file",
                "vendor": "claude",
                "row": _dispatch_observed_no_telemetry_row("code-reviewer", RP.P_PANEL),
            }],
            RP.P_VERIFIERS: [{
                "seat": "verifier-seat",
                "channel": "file",
                "vendor": "claude",
                "row": _dispatch_observed_no_telemetry_row("verifier-seat", RP.P_VERIFIERS),
            }],
        },
        True,
    ),
    (
        "one_qualified_panel_plus_excluded_mixed",
        {
            RP.P_PANEL: [
                {
                    "seat": "security-reviewer",
                    "channel": "stdout",
                    "vendor": "codex",
                    "row": _qualifying_dispatch_row("security-reviewer", RP.P_PANEL),
                },
                {
                    "seat": "code-reviewer",
                    "channel": "file",
                    "vendor": "claude",
                    "row": _dispatch_observed_no_telemetry_row("code-reviewer", RP.P_PANEL),
                },
            ],
            RP.P_VERIFIERS: [{
                "seat": "verifier-seat",
                "channel": "file",
                "vendor": "claude",
                "row": _dispatch_observed_no_telemetry_row("verifier-seat", RP.P_VERIFIERS),
            }],
            RP.P_GAPSWEEP: [{
                "seat": "gapsweep-seat",
                "channel": "file",
                "vendor": "claude",
                "row": _dispatch_observed_no_telemetry_row("gapsweep-seat", RP.P_GAPSWEEP),
            }],
            RP.P_SCOPED: [{
                "seat": "scoped-seat",
                "channel": "file",
                "vendor": "claude",
                "row": _dispatch_observed_no_telemetry_row("scoped-seat", RP.P_SCOPED),
            }],
            RP.P_SYNTHESIS: [{
                "seat": "synthesis-seat",
                "channel": "file",
                "vendor": "claude",
                "row": _dispatch_observed_no_telemetry_row("synthesis-seat", RP.P_SYNTHESIS),
            }],
        },
        True,
    ),
))
def test_l4a_host_channel_refusal_census(tmp_path, case_id, phase_specs, expect_refusal):
    """R28: host-channel seats without runner evidence refuse per-seat unrun-review."""
    session_dir = _multi_phase_session(tmp_path, phase_specs)
    ctx, err = RC._load_context(session_dir)
    assert err is None
    refusal = RC.check_unrun_review(ctx)
    assert expect_refusal
    assert refusal is not None
    assert refusal["class"] == "unrun-review"
    assert refusal["bindingFailure"] == "execution-evidence-absent"


# --- edge 8: every panel seat uncertified → floor refusal --------------------------------


def test_l4a_edge8_all_panel_seats_host_channel_refuse(tmp_path):
    seat = "code-reviewer"
    row = _dispatch_observed_no_telemetry_row(seat, RP.P_PANEL)
    session_dir, _ = _session_with_manifest(
        tmp_path,
        seat=seat,
        phase=RP.P_PANEL,
        channel="file",
        vendor="claude",
        journal_lines=[row],
        envelopes=[{"seat": seat, "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}],
    )
    ctx, err = RC._load_context(session_dir)
    assert err is None
    refusal = RC.check_unrun_review(ctx)
    assert refusal is not None
    assert refusal["class"] == "unrun-review"
    assert refusal["artifact"] == seat
    assert refusal["bindingFailure"] == "execution-evidence-absent"


# --- edge 9: no recorded panel seat → unchanged ------------------------------------------


def test_l4a_edge9_no_panel_seat_unchanged(tmp_path):
    phase = RP.P_VERIFIERS
    seat = "verifier-seat"
    row = _dispatch_observed_no_telemetry_row(seat, phase)
    session_dir, _ = _session_with_manifest(
        tmp_path,
        seat=seat,
        phase=phase,
        channel="stdout",
        vendor="codex",
        journal_lines=[row],
        envelopes=[{"seat": seat, "phase": phase, "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}],
    )
    ctx, err = RC._load_context(session_dir)
    assert err is None
    refusal = RC.check_unrun_review(ctx)
    assert refusal is not None
    assert refusal["class"] == "unrun-review"
    assert refusal["artifact"] == seat


# --- edge 10: host with qualifying telemetry → certified, not named ------------------------


def test_l4a_edge10_host_with_telemetry_certified_not_named(tmp_path):
    seat = "code-reviewer"
    row = _dispatch_journal_with_binding(seat=seat)
    session_dir, _ = _session_with_manifest(
        tmp_path,
        seat=seat,
        phase=RP.P_PANEL,
        channel="file",
        vendor="claude",
        journal_lines=[row],
        envelopes=[{"seat": seat, "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}],
    )
    ctx, err = RC._load_context(session_dir)
    assert err is None
    assert RC.check_unrun_review(ctx) is None


def test_l4a_edge10b_host_present_evidence_wrong_head_refuses(tmp_path):
    """Host file-channel seat with runner evidence bound to a stale head must refuse, not disclose."""
    seat = "code-reviewer"
    row = _dispatch_journal_with_binding(seat=seat, head_sha="b" * 40)
    session_dir, _ = _session_with_manifest(
        tmp_path,
        seat=seat,
        phase=RP.P_PANEL,
        channel="file",
        vendor="claude",
        journal_lines=[row],
        envelopes=[{"seat": seat, "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}],
    )
    ctx, err = RC._load_context(session_dir)
    assert err is None
    refusal = RC.check_unrun_review(ctx)
    assert refusal is not None
    assert refusal["class"] == "unrun-review"
    assert refusal["artifact"] == seat
    assert refusal.get("bindingFailure") != "execution-evidence-absent"


# --- hand-landed qualifying panel + host without telemetry → host refuses -------------------


def _panel_hand_landed_plus_host_uncertified_session(tmp_path):
    hand_seat = "security-reviewer"
    host_seat = "code-reviewer"
    evidence = {
        **_binding_fields("hand-nonce", result_digest=DEFAULT_FINDINGS_RESULT_SHA),
        "runKind": SC.RUN_KIND_REVIEW,
        "observation": {
            "read": "engaged",
            "source": "runner",
            "telemetry": "tool-calls",
            "stdoutBytes": 10,
            "wallSeconds": 1.0,
        },
    }
    hand_row = _hand_landed_binding_journal_row(
        hand_seat, DEFAULT_PANEL_PAYLOAD_SHA, evidence)
    host_row = _dispatch_observed_no_telemetry_row(host_seat, RP.P_PANEL)
    skey_hand, hand_entry = _manifest_seat_entry(hand_seat, "stdout", "codex")
    skey_host, host_entry = _manifest_seat_entry(host_seat, "file", "claude")
    manifest = {
        "schema": "orders-manifest/1",
        "session": "test-session-001",
        "round": 1,
        "phase": RP.P_PANEL,
        "attempt": 0,
        "orders": "not-emitted",
        "seats": {skey_hand: hand_entry, skey_host: host_entry},
    }
    manifest_sha = SC.sha256_text(SC.canonical(manifest))
    envelopes = [
        {
            "seat": hand_seat,
            "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA,
            "provenance": "hand-landed",
            "executionEvidence": evidence,
        },
        {"seat": host_seat, "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA},
    ]
    session_dir = write_session(
        tmp_path,
        journal_lines=[
            hand_row,
            host_row,
            _orders_emitted_journal_row(manifest_sha),
        ],
        envelopes=envelopes,
    )
    _write_orders_manifest(session_dir, manifest)
    return session_dir, host_seat


def test_l4a_hand_landed_panel_plus_host_refuses_host_seat(tmp_path):
    """R28: qualifying hand-landed panel seat does not exempt host panel seat."""
    session_dir, host_seat = _panel_hand_landed_plus_host_uncertified_session(tmp_path)
    ctx, err = RC._load_context(session_dir)
    assert err is None
    refusal = RC.check_unrun_review(ctx)
    assert refusal is not None
    assert refusal["class"] == "unrun-review"
    assert refusal["artifact"] == host_seat
    assert refusal["bindingFailure"] == "execution-evidence-absent"


# --- T-nomutate: _build_receipt must not mutate state seat-map rows ---------------------


def test_l4a_t_nomutate_build_receipt_does_not_mutate_state_seat_map_rows(tmp_path):
    session_dir = _panel_host_uncertified_session(tmp_path)
    ctx, err = RC._load_context(session_dir)
    assert err is None
    state = ctx["state"]
    state["seatMapReceipts"] = [{
        "round": "1",
        "map": {
            "seats": {
                "code-reviewer": {"vendor": "claude", "model": "sonnet"},
                "security-reviewer": {"vendor": "codex", "model": "gpt"},
            },
        },
    }]
    assert RC.check_unrun_review(ctx) is not None
    receipt, refusal = RC._build_receipt(ctx, "certified", None)
    assert refusal is None
    assert receipt is not None
    for entry in state.get("seatMapReceipts") or []:
        seats = (entry.get("map") or {}).get("seats") or {}
        for row in seats.values():
            if isinstance(row, dict):
                assert "certifiedPanel" not in row
    receipt_seats = (receipt.get("seatMap") or {}).get("seats") or {}
    assert "certifiedPanel" not in receipt_seats.get("code-reviewer", {})
    assert "certifiedPanel" not in receipt_seats.get("security-reviewer", {})


# --- edge 11: malformed receipt additions → validator refuses -----------------------------


def _minimal_valid_receipt(**overrides):
    receipt = {
        "disclosures": {
            "importantOutOfScope": [],
        },
        "seatMap": {"seats": {"code-reviewer": {"vendor": "claude"}}},
        "independence": {"auditSeats": []},
    }
    receipt.update(overrides)
    return receipt


def test_l4a_edge11_no_uncertified_seats_key_on_receipt():
    """R28: certified receipt shape omits retired disclosures.uncertifiedSeats."""
    receipt = _minimal_valid_receipt()
    refusal = RC._validate_receipt_additions(receipt)
    assert refusal is None
    assert "uncertifiedSeats" not in receipt["disclosures"]


def test_l4a_edge11_no_certified_panel_validator():
    """R28: retired certifiedPanel receipt validator removed."""
    receipt = _minimal_valid_receipt()
    receipt["seatMap"]["seats"]["code-reviewer"]["certifiedPanel"] = "yes"
    refusal = RC._validate_receipt_additions(receipt)
    assert refusal is None


def test_l4a_edge11_bad_audit_model_refuses():
    receipt = _minimal_valid_receipt()
    receipt["independence"]["auditSeats"] = [{"seat": "t1", "model": ""}]
    refusal = RC._validate_receipt_additions(receipt)
    assert refusal is not None
    assert refusal["class"] == "unfetched-findings"


# --- T-manifest: emit writes channel for claude (file) and codex (stdout) ------------------


def test_l4a_manifest_emits_channel_for_claude_and_codex_panel_seats(tmp_path):
    RD = _load_round_driver()
    spec = importlib.util.spec_from_file_location(
        "round_records", os.path.join(_LIB, "round_records.py"))
    RR = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(RR)

    DIFF = "diff --git a/a.py b/a.py\n"
    session_dir = str(tmp_path / "manifest-channel")
    os.makedirs(session_dir, exist_ok=True)
    seat_map = {
        "seats": {
            RD.DIMENSIONS[0]: {"vendor": "codex", "model": "gpt", "engine": "codex"},
            RD.DIMENSIONS[1]: {"vendor": "claude", "model": "sonnet", "engine": "claude"},
        }
    }
    out = RD.cmd_next(session_dir, {
        "leg": "code", "vendors": ["claude", "codex"], "diff": DIFF,
        "fixerVendor": "claude", "verifyCommand": "none", "seatMap": seat_map,
    })
    assert out["ok"], out
    ok, state = RD.load_state(session_dir)
    assert ok, state
    pend = state["pending"]
    manifest_path = RD._orders_manifest_path(
        session_dir, pend["round"], RD.P_PANEL, pend["attempt"])
    manifest, err = RR.read_json(manifest_path)
    assert err is None, err
    channels = {}
    for entry in manifest["seats"].values():
        channels[entry["seat"]] = entry.get("channel")
    assert channels[RD.DIMENSIONS[0]] == RD.CHANNEL_STDOUT
    assert channels[RD.DIMENSIONS[1]] == RD.CHANNEL_FILE


# --- T-R5: round_certification has no round_driver import --------------------------------


def test_l4a_round_certification_has_no_round_driver_import():
    path = os.path.join(_LIB, "round_certification.py")
    with open(path, encoding="utf-8") as fh:
        source = fh.read()
    assert "import round_driver" not in source
    assert "from round_driver" not in source


# --- T-reuse: _orders_emitted_roster_or_refusal byte-identical behaviours ------------------


def test_l4a_reuse_orders_emitted_roster_valid_manifest(tmp_path):
    manifest = _minimal_orders_manifest()
    manifest_sha = SC.sha256_text(SC.canonical(manifest))
    session_dir = write_session(tmp_path, journal_lines=[])
    _write_orders_manifest(session_dir, manifest)
    event = _orders_emitted_journal_row(manifest_sha)
    roster, refusal = RC._orders_emitted_roster_or_refusal(session_dir, event)
    assert refusal is None
    assert roster == [("security-reviewer", 0)]


def test_l4a_reuse_orders_emitted_roster_tampered_manifest(tmp_path):
    manifest = _minimal_orders_manifest()
    session_dir = write_session(tmp_path, journal_lines=[])
    _write_orders_manifest(session_dir, manifest)
    event = _orders_emitted_journal_row("b" * 64)
    roster, refusal = RC._orders_emitted_roster_or_refusal(session_dir, event)
    assert roster is None
    assert refusal is not None
    assert refusal["class"] == "unfetched-findings"
    assert "sha256" in refusal["detail"]
