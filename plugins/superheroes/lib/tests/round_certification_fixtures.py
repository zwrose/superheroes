"""Shared fixture helpers for round_certification tests — test tree only, no driver imports."""
import json
import os

import round_certification as RC
import round_records as RR

META_FILE = "meta.json"
STATE_FILE = "loop-state.json"
JOURNAL_FILE = "driver-journal.jsonl"


def write_session(
    tmp_path,
    *,
    name="session",
    state=None,
    journal_lines=None,
    meta=None,
    envelopes=None,
):
    session_dir = str(tmp_path / name)
    os.makedirs(session_dir, exist_ok=True)
    meta_obj = {"sessionId": "test-session-001", "headSha": "a" * 40}
    if meta:
        meta_obj.update(meta)
    with open(os.path.join(session_dir, META_FILE), "w", encoding="utf-8") as fh:
        json.dump(meta_obj, fh, sort_keys=True)
    state_obj = _minimal_terminal_state()
    if state:
        state_obj.update(state)
    with open(os.path.join(session_dir, STATE_FILE), "w", encoding="utf-8") as fh:
        json.dump(state_obj, fh, sort_keys=True)
    lines = journal_lines if journal_lines is not None else [_default_journal_row()]
    with open(os.path.join(session_dir, JOURNAL_FILE), "w", encoding="utf-8") as fh:
        for row in lines:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    for spec in envelopes if envelopes is not None else [{"seat": "code-reviewer", "payloadSha256": "abc123"}]:
        _write_envelope(session_dir, spec)
    return session_dir


def _minimal_terminal_state():
    head = "a" * 40
    return {
        "schemaVersion": 5,
        "config": {
            "fixerVendor": "claude",
            "baseGuard": RC.BASE_GUARD_CHECKED,
            "headSha": head,
        },
        "round": 1,
        "step": "terminal",
        "terminal": "converged",
        "certification": {
            "shape": "full-panel-confirmed",
            "fullPanel": True,
            "independence": "independent",
            "base": "fetched",
            "pluginVersionSkew": "not-checked",
            "shapeDrivers": [],
        },
        "findings": [
            {
                "id": "F1",
                "file": "a.py",
                "line": 1,
                "title": "issue",
                "severity": "Minor",
                "disposition": "fixed",
                "dispositionReceipt": {"headSha": head, "verifyResult": "pass"},
            }
        ],
        "decisions": [{"round": 1, "kind": "converged", "detail": "certified"}],
        "rounds": {},
        "seatMapReceipts": [
            {
                "round": "1",
                "map": {
                    "seats": {
                        "code-reviewer": {"vendor": "codex", "model": "gpt-5.6-sol"},
                    }
                },
            }
        ],
    }


def _default_journal_row():
    return {
        "cmd": "record-result",
        "outcome": "recorded",
        "phase": "dispatch-panel",
        "round": 1,
        "attempt": 0,
        "seat": "code-reviewer",
        "occurrence": 0,
        "provenance": "dispatch-observed",
        "payloadSha256": "abc123",
        "executionEvidence": {
            "read": "engaged",
            "source": "runner",
            "telemetry": "tool-calls",
            "stdoutBytes": 10,
            "wallSeconds": 1.0,
        },
        "recordIdentity": {
            "phase": "dispatch-panel",
            "seat": "code-reviewer",
            "occurrence": 0,
            "attempt": 0,
        },
    }


def _write_envelope(session_dir, spec):
    rnd = spec.get("round", 1)
    phase = spec.get("phase", "dispatch-panel")
    seat = spec["seat"]
    attempt = spec.get("attempt", 0)
    occurrence = spec.get("occurrence", 0)
    skey = RC._storage_key(seat, occurrence)
    path = os.path.join(
        session_dir,
        "round-%d" % rnd,
        "seats",
        phase,
        "%s.a%d.json" % (skey, attempt),
    )
    os.makedirs(os.path.dirname(path), exist_ok=True)
    envelope = spec.get("envelope") or {
        "schema": "seat-result/2",
        "session": "test-session-001",
        "round": rnd,
        "phase": phase,
        "seat": seat,
        "attempt": attempt,
        "vendor": "codex",
        "model": "gpt-5.6-sol",
        "payloadSha256": spec.get("payloadSha256", "abc123"),
        "provenance": spec.get("provenance", "dispatch-observed"),
        "payload": {"findings": []},
        "executionEvidence": spec.get(
            "executionEvidence",
            {
                "source": "runner",
                "runnerNonce": "nonce",
                "recordDigest": "d" * 64,
                "resultDigest": "e" * 64,
                "resultKind": "findings",
                "observation": {
                    "read": "engaged",
                    "source": "runner",
                    "telemetry": "tool-calls",
                    "stdoutBytes": 10,
                    "wallSeconds": 1.0,
                },
            },
        ),
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(envelope, fh, sort_keys=True)


HEAD_SHA = "a" * 40


def parity_converged_single_round(tmp_path):
    """Converged single-round session with one baseline round entry."""
    return write_session(
        tmp_path,
        name="converged-single",
        state={
            "rounds": {
                "1": {
                    "roundKind": "baseline",
                    "seatStatus": {"code-reviewer": "run"},
                    "blockingCount": 0,
                    "verifyResult": "pass",
                    "verifyPasses": [],
                }
            }
        },
    )


def parity_multi_round_fix(tmp_path):
    """Multi-round session whose second round is a fix round."""
    return write_session(
        tmp_path,
        name="multi-fix",
        state={
            "round": 2,
            "rounds": {
                "1": {
                    "roundKind": "baseline",
                    "seatStatus": {"code-reviewer": "run"},
                    "blockingCount": 1,
                    "verifyResult": "pass",
                    "verifyPasses": [],
                },
                "2": {
                    "roundKind": "fix",
                    "seatStatus": {"code-reviewer": "run"},
                    "blockingCount": 0,
                    "verifyResult": "pass",
                    "verifyPasses": [],
                    "selfRecovery": False,
                },
            },
            "decisions": [
                {"round": 1, "kind": "verify-skip-but-configured", "detail": "skipped"},
                {"round": 2, "kind": "converged", "detail": "certified"},
            ],
        },
    )


def parity_disclosure_channels(tmp_path):
    """Session whose round carries per-round disclosure channels."""
    return write_session(
        tmp_path,
        name="disclosures",
        state={
            "rounds": {
                "1": {
                    "roundKind": "baseline",
                    "seatStatus": {"code-reviewer": "run"},
                    "blockingCount": 0,
                    "verifyResult": "pass",
                    "verifyPasses": [
                        {
                            "CONFIRMED": 1,
                            "PLAUSIBLE": 0,
                            "REFUTED": 0,
                            "drops": 0,
                            "downgrades": 0,
                            "unverified": 0,
                            "ambiguous": 0,
                        }
                    ],
                    "canaryUnverified": ["code-reviewer"],
                    "vacuousSeats": ["architecture-reviewer"],
                    "fellOpen": [
                        {
                            "seat": "test-reviewer",
                            "configured": "codex",
                            "reason": "forfeit",
                            "ran": "claude",
                        }
                    ],
                }
            }
        },
    )


def parity_skipped_blockers(tmp_path):
    """Session carrying owner-skipped judgment blockers."""
    return write_session(
        tmp_path,
        name="skipped-blockers",
        state={
            "_skippedBlockers": [
                {
                    "id": "B1",
                    "title": "tradeoff blocker",
                    "severity": "Important",
                    "file": "b.py",
                    "line": 2,
                    "reason": "owner accepted risk",
                }
            ],
            "rounds": {
                "1": {
                    "roundKind": "baseline",
                    "seatStatus": {"code-reviewer": "run"},
                    "blockingCount": 0,
                    "verifyResult": "pass",
                    "verifyPasses": [],
                }
            },
        },
    )


def parity_seat_map_degradations(tmp_path):
    """Session with seat-map/base degradations reflected in receipt prose."""
    return write_session(
        tmp_path,
        name="seat-map-degraded",
        state={
            "independenceDegraded": True,
            "config": {
                "fixerVendor": "claude",
                "baseGuard": RC.BASE_GUARD_CHECKED,
                "headSha": HEAD_SHA,
                "baseDegraded": True,
                "baseFetch": "degraded",
            },
            "certification": {
                "shape": "full-panel-confirmed-degraded",
                "fullPanel": True,
                "independence": "degraded",
                "base": "degraded",
                "pluginVersionSkew": "not-checked",
                "shapeDrivers": ["independence", "base"],
            },
            "rounds": {
                "1": {
                    "roundKind": "baseline",
                    "seatStatus": {"code-reviewer": "run"},
                    "blockingCount": 0,
                    "verifyResult": "pass",
                    "verifyPasses": [],
                }
            },
        },
    )


def parity_policy_and_base(tmp_path):
    """Session with policyApplied and a populated base block."""
    return write_session(
        tmp_path,
        name="policy-base",
        meta={"mode": "branch", "headSha": HEAD_SHA},
        state={
            "config": {
                "fixerVendor": "claude",
                "baseGuard": RC.BASE_GUARD_CHECKED,
                "headSha": HEAD_SHA,
                "baseRef": HEAD_SHA,
                "baseBranch": "main",
                "baseFetch": "fetched",
                "baseRepo": "origin",
                "repoRoot": "/tmp/repo",
            },
            "_policyApplied": [
                {
                    "source": "gate-policy",
                    "phase": "dispatch-judgment",
                    "detail": "pre-authorized skip",
                }
            ],
            "rounds": {
                "1": {
                    "roundKind": "baseline",
                    "seatStatus": {"code-reviewer": "run"},
                    "blockingCount": 0,
                    "verifyResult": "pass",
                    "verifyPasses": [],
                }
            },
        },
    )


def parity_capped_terminal(tmp_path):
    """Capped terminal with open critical findings."""
    return write_session(
        tmp_path,
        name="capped",
        state={
            "terminal": "capped-with-open-critical",
            "findings": [
                {
                    "id": "F1",
                    "file": "a.py",
                    "line": 1,
                    "title": "critical open",
                    "severity": "Critical",
                    "disposition": "refuted",
                    "dispositionReceipt": "owner accepted residual risk for cap",
                }
            ],
            "decisions": [
                {
                    "round": 1,
                    "kind": "capped-with-open-critical",
                    "detail": "open findings remain",
                }
            ],
            "certification": {
                "shape": "capped-with-open-critical",
                "fullPanel": True,
                "independence": "independent",
                "base": "fetched",
                "pluginVersionSkew": "not-checked",
                "shapeDrivers": [],
            },
            "rounds": {
                "1": {
                    "roundKind": "baseline",
                    "seatStatus": {"code-reviewer": "run"},
                    "blockingCount": 1,
                    "verifyResult": "pass",
                    "verifyPasses": [],
                }
            },
        },
    )


def parity_halted_terminal(tmp_path):
    """Halted terminal after verify failure."""
    return write_session(
        tmp_path,
        name="halted",
        state={
            "terminal": "halted",
            "decisions": [
                {"round": 1, "kind": "verify-fail", "detail": "verify gate failed"}
            ],
            "certification": {
                "shape": "halted",
                "fullPanel": False,
                "independence": "independent",
                "base": "fetched",
                "pluginVersionSkew": "not-checked",
                "shapeDrivers": [],
            },
            "rounds": {
                "1": {
                    "roundKind": "baseline",
                    "seatStatus": {"code-reviewer": "run"},
                    "blockingCount": 0,
                    "verifyResult": "fail",
                    "verifyPasses": [],
                }
            },
        },
    )


PARITY_FIXTURES = (
    ("converged-single-round", parity_converged_single_round),
    ("multi-round-fix", parity_multi_round_fix),
    ("disclosure-channels", parity_disclosure_channels),
    ("skipped-blockers", parity_skipped_blockers),
    ("seat-map-degradations", parity_seat_map_degradations),
    ("policy-and-base", parity_policy_and_base),
    ("capped-terminal", parity_capped_terminal),
    ("halted-terminal", parity_halted_terminal),
)

# --- WO-L2-K six-case and FR-D2 specimen fixtures --------------------------------

AUDIT_PHASE = "dispatch-audits"
PANEL_PHASE = RC.PANEL_PHASE
HEAD_CONTENT_BLOBS_FILE = "head-content-blobs.json"
SIXTEEN_AUDIT_SEATS = tuple("audit-target-%02d" % i for i in range(16))
ANCHOR_SHA = "feb91032a2cb2106f089a25063b8178527ae4359f5412ccf549e9d2f98f28ce9"

_HAND_LANDED_EXECUTION_EVIDENCE = {
    "source": "runner",
    "runnerNonce": "nonce-six-cases",
    "recordDigest": "d" * 64,
    "resultDigest": "e" * 64,
    "resultKind": "findings",
    "observation": {
        "read": "engaged",
        "source": "runner",
        "telemetry": "tool-calls",
        "stdoutBytes": 10,
        "wallSeconds": 1.0,
    },
}


def _dispatch_observed_journal_row(seat, payload_sha, *, attempt=0, head_sha=None):
    row = {
        "cmd": "record-result",
        "outcome": "recorded",
        "phase": PANEL_PHASE,
        "round": 1,
        "attempt": attempt,
        "seat": seat,
        "provenance": RC.PROVENANCE_DISPATCH_OBSERVED,
        "payloadSha256": payload_sha,
        "executionEvidence": {
            "read": "engaged",
            "source": "runner",
            "telemetry": "tool-calls",
            "stdoutBytes": 10,
            "wallSeconds": 1.0,
        },
        "recordIdentity": {
            "phase": PANEL_PHASE,
            "seat": seat,
            "occurrence": 0,
            "attempt": attempt,
        },
    }
    if head_sha is not None:
        row["headSha"] = head_sha
    return row


def _hand_landed_journal_row(seat, payload_sha, *, phase=PANEL_PHASE, attempt=0):
    return {
        "cmd": "record-result",
        "outcome": "recorded",
        "phase": phase,
        "round": 1,
        "attempt": attempt,
        "seat": seat,
        "provenance": RC.PROVENANCE_HAND_LANDED,
        "payloadSha256": payload_sha,
        "recordIdentity": {
            "phase": phase,
            "seat": seat,
            "occurrence": 0,
            "attempt": attempt,
        },
    }


def _hand_landed_envelope(seat, payload, *, phase=PANEL_PHASE, attempt=0, evidence=None):
    evidence_obj = evidence if evidence is not None else _HAND_LANDED_EXECUTION_EVIDENCE
    envelope = {
        "schema": "seat-result/2",
        "session": "test-session-001",
        "round": 1,
        "phase": phase,
        "seat": seat,
        "attempt": attempt,
        "vendor": "codex",
        "model": "gpt-5.6-sol",
        "payload": payload,
        "payloadSha256": RR.payload_sha256(payload),
        "provenance": RC.PROVENANCE_HAND_LANDED,
        "manifestSha256": ANCHOR_SHA,
        "orderSha256": ANCHOR_SHA,
        "executionEvidence": evidence_obj,
        "envelopeSha256": RR.envelope_sha256(payload, evidence_obj),
    }
    return envelope


def _write_head_content_blobs(session_dir, blobs):
    path = os.path.join(session_dir, HEAD_CONTENT_BLOBS_FILE)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(blobs, fh, sort_keys=True)


def case01_recovered_seat(tmp_path):
    """Required seat failed once then recovered by a later qualifying result."""
    return write_session(
        tmp_path,
        name="case-01-recovered-seat",
        journal_lines=[
            {
                "cmd": "record-result",
                "outcome": "failed",
                "phase": PANEL_PHASE,
                "round": 1,
                "attempt": 0,
                "seat": "code-reviewer",
                "provenance": RC.PROVENANCE_DISPATCH_OBSERVED,
                "payloadSha256": "failed-attempt-sha",
                "recordIdentity": {
                    "phase": PANEL_PHASE,
                    "seat": "code-reviewer",
                    "occurrence": 0,
                    "attempt": 0,
                },
            },
            _dispatch_observed_journal_row("code-reviewer", "recovered-sha", attempt=1),
        ],
        envelopes=[{"seat": "code-reviewer", "payloadSha256": "recovered-sha", "attempt": 1}],
    )


def case02_unrecovered_seat(tmp_path):
    """Required seat failed and was never recovered — no landed envelope."""
    return write_session(
        tmp_path,
        name="case-02-unrecovered-seat",
        journal_lines=[
            {
                "cmd": "record-result",
                "outcome": "failed",
                "phase": PANEL_PHASE,
                "round": 1,
                "attempt": 0,
                "seat": "code-reviewer",
                "provenance": RC.PROVENANCE_DISPATCH_OBSERVED,
                "recordIdentity": {
                    "phase": PANEL_PHASE,
                    "seat": "code-reviewer",
                    "occurrence": 0,
                    "attempt": 0,
                },
            }
        ],
        envelopes=[],
    )


def case03_reverted_fix(tmp_path):
    """Fixed disposition whose on-head content was reverted by a later commit on the same head."""
    session_dir = write_session(
        tmp_path,
        name="case-03-reverted-fix",
        state={
            "findings": [
                {
                    "id": "F-fix",
                    "file": "src/guard.py",
                    "line": 12,
                    "title": "missing bounds guard",
                    "severity": "Important",
                    "disposition": "fixed",
                    "dispositionReceipt": {
                        "headSha": HEAD_SHA,
                        "verifyResult": "pass",
                    },
                }
            ]
        },
        journal_lines=[_dispatch_observed_journal_row("code-reviewer", "verify-sha")],
        envelopes=[{"seat": "code-reviewer", "payloadSha256": "verify-sha"}],
    )
    _write_head_content_blobs(
        session_dir,
        {
            "headSha": HEAD_SHA,
            "files": {
                "src/guard.py": "# fix landed then reverted on the same head\npass\n",
            },
            "fixCommits": [
                {"headSha": HEAD_SHA, "path": "src/guard.py", "present": True},
                {"headSha": HEAD_SHA, "path": "src/guard.py", "present": False},
            ],
        },
    )
    return session_dir


def case04_stale_cited_head(tmp_path):
    """Seat result whose cited head is older than the certified head."""
    stale = "b" * 40
    return write_session(
        tmp_path,
        name="case-04-stale-head",
        meta={"headSha": HEAD_SHA},
        journal_lines=[
            _dispatch_observed_journal_row("code-reviewer", "stale-sha", head_sha=stale)
        ],
        envelopes=[{"seat": "code-reviewer", "payloadSha256": "stale-sha"}],
    )


def case05_critical_out_of_scope(tmp_path):
    """Critical finding carried out of scope despite an otherwise-valid follow-up."""
    return write_session(
        tmp_path,
        name="case-05-critical-oos",
        state={
            "findings": [
                {
                    "id": "C-oos",
                    "severity": "Critical",
                    "disposition": "out-of-scope",
                    "followUp": {
                        "revisitTrigger": "milestone M2",
                        "classClosure": "none",
                    },
                }
            ]
        },
        journal_lines=[_dispatch_observed_journal_row("code-reviewer", "panel-sha")],
        envelopes=[{"seat": "code-reviewer", "payloadSha256": "panel-sha"}],
    )


def case05_critical_skipped(tmp_path):
    """Critical finding skipped — must refuse disposition-without-receipt."""
    return write_session(
        tmp_path,
        name="case-05-critical-skipped",
        state={
            "findings": [
                {
                    "id": "C-skip",
                    "severity": "Critical",
                    "disposition": "skipped",
                }
            ]
        },
        journal_lines=[_dispatch_observed_journal_row("code-reviewer", "panel-sha")],
        envelopes=[{"seat": "code-reviewer", "payloadSha256": "panel-sha"}],
    )


def case06_mixed_panel(tmp_path):
    """Panel mixing hand-landed and dispatch-observed seats."""
    dispatch_sha = "dispatch-sha"
    hand_payload = {"findings": []}
    hand_sha = RR.payload_sha256(hand_payload)
    return write_session(
        tmp_path,
        name="case-06-mixed-panel",
        state={
            "certification": {
                "shape": "full-panel-confirmed",
                "fullPanel": True,
                "independence": "independent",
                "base": "fetched",
                "pluginVersionSkew": "not-checked",
                "shapeDrivers": [],
            }
        },
        journal_lines=[
            _dispatch_observed_journal_row("code-reviewer", dispatch_sha),
            _hand_landed_journal_row("security-reviewer", hand_sha),
        ],
        envelopes=[
            {
                "seat": "code-reviewer",
                "payloadSha256": dispatch_sha,
                "provenance": RC.PROVENANCE_DISPATCH_OBSERVED,
            },
            {
                "seat": "security-reviewer",
                "payloadSha256": hand_sha,
                "provenance": RC.PROVENANCE_HAND_LANDED,
                "envelope": _hand_landed_envelope(
                    "security-reviewer",
                    hand_payload,
                ),
            },
        ],
    )


def specimen_must_certify_sixteen_seat_audit(tmp_path):
    """FR-D2 must-certify: sixteen-seat out-of-manifest hand-landed audit panel."""
    journal_lines = []
    envelope_specs = []
    for seat in SIXTEEN_AUDIT_SEATS:
        payload = {"findings": [{"id": seat, "severity": "Minor", "title": "audit ok"}]}
        payload_sha = RR.payload_sha256(payload)
        journal_lines.append(
            _hand_landed_journal_row(seat, payload_sha, phase=AUDIT_PHASE)
        )
        envelope_specs.append(
            {
                "seat": seat,
                "phase": AUDIT_PHASE,
                "payloadSha256": payload_sha,
                "provenance": RC.PROVENANCE_HAND_LANDED,
                "envelope": _hand_landed_envelope(seat, payload, phase=AUDIT_PHASE),
            }
        )
    return write_session(
        tmp_path,
        name="specimen-must-certify-audit",
        state={
            "certification": {
                "shape": "full-panel-confirmed",
                "fullPanel": True,
                "independence": "independent",
                "base": "fetched",
                "pluginVersionSkew": "not-checked",
                "shapeDrivers": [],
            }
        },
        journal_lines=journal_lines,
        envelopes=envelope_specs,
    )


def specimen_refuse_bare_fabricated_findings(tmp_path):
    """FR-D2 (a): bare fabricated findings on disk with no envelope."""
    session_dir = write_session(
        tmp_path,
        name="specimen-refuse-bare-findings",
        journal_lines=[
            _hand_landed_journal_row("code-reviewer", "fabricated-sha")
        ],
        envelopes=[],
    )
    findings_path = os.path.join(session_dir, "findings-code.json")
    with open(findings_path, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "findings": [
                    {
                        "id": "fabricated-001",
                        "severity": "Important",
                        "title": "never executed",
                    }
                ]
            },
            fh,
            sort_keys=True,
        )
    return session_dir


def specimen_refuse_fabricated_envelope_audited_chain(tmp_path):
    """FR-D2 (b): well-formed hand-landed envelope over fabricated findings."""
    payload = {
        "findings": [
            {
                "id": "fabricated-002",
                "severity": "Important",
                "title": "authored but never executed",
            }
        ]
    }
    payload_sha = RR.payload_sha256(payload)
    envelope = _hand_landed_envelope("code-reviewer", payload)
    return write_session(
        tmp_path,
        name="specimen-refuse-fabricated-envelope",
        state={
            "certification": {
                "shape": "full-panel-confirmed",
                "fullPanel": True,
            }
        },
        journal_lines=[_hand_landed_journal_row("code-reviewer", payload_sha)],
        envelopes=[
            {
                "seat": "code-reviewer",
                "payloadSha256": payload_sha,
                "provenance": RC.PROVENANCE_HAND_LANDED,
                "envelope": envelope,
            }
        ],
    )


def specimen_refuse_caller_supplied_execution_evidence(tmp_path):
    """FR-D2 (c): caller-supplied file placed in the execution-evidence slot."""
    payload = {"findings": []}
    payload_sha = RR.payload_sha256(payload)
    evidence = dict(_HAND_LANDED_EXECUTION_EVIDENCE)
    evidence["source"] = "/tmp/caller-minted-evidence.json"
    envelope = _hand_landed_envelope("code-reviewer", payload, evidence=evidence)
    return write_session(
        tmp_path,
        name="specimen-refuse-caller-evidence",
        journal_lines=[_hand_landed_journal_row("code-reviewer", payload_sha)],
        envelopes=[
            {
                "seat": "code-reviewer",
                "payloadSha256": payload_sha,
                "provenance": RC.PROVENANCE_HAND_LANDED,
                "envelope": envelope,
            }
        ],
    )


def base_guard_not_checked_session(tmp_path):
    return write_session(
        tmp_path,
        name="base-guard-not-checked",
        state={
            "config": {
                "fixerVendor": "claude",
                "baseGuard": "not-checked",
                "headSha": HEAD_SHA,
            }
        },
        journal_lines=[_dispatch_observed_journal_row("code-reviewer", "panel-sha")],
        envelopes=[{"seat": "code-reviewer", "payloadSha256": "panel-sha"}],
    )


def followup_missing_class_closure(tmp_path):
    return write_session(
        tmp_path,
        name="followup-missing-class-closure",
        state={
            "findings": [
                {
                    "id": "I-missing-closure",
                    "severity": "Important",
                    "disposition": "out-of-scope",
                    "followUp": {"revisitTrigger": "2026-12-01"},
                }
            ]
        },
        journal_lines=[_dispatch_observed_journal_row("code-reviewer", "panel-sha")],
        envelopes=[{"seat": "code-reviewer", "payloadSha256": "panel-sha"}],
    )


def followup_class_closure_none(tmp_path):
    return write_session(
        tmp_path,
        name="followup-class-closure-none",
        state={
            "findings": [
                {
                    "id": "I-none-closure",
                    "severity": "Important",
                    "disposition": "out-of-scope",
                    "followUp": {
                        "revisitTrigger": "2026-12-01",
                        "classClosure": "none",
                    },
                }
            ]
        },
        journal_lines=[_dispatch_observed_journal_row("code-reviewer", "panel-sha")],
        envelopes=[{"seat": "code-reviewer", "payloadSha256": "panel-sha"}],
    )


def followup_no_revisit_trigger(tmp_path):
    return write_session(
        tmp_path,
        name="followup-no-revisit-trigger",
        state={
            "findings": [
                {
                    "id": "I-no-trigger",
                    "severity": "Important",
                    "disposition": "out-of-scope",
                    "followUp": {"classClosure": "tracked in issue-42"},
                }
            ]
        },
        journal_lines=[_dispatch_observed_journal_row("code-reviewer", "panel-sha")],
        envelopes=[{"seat": "code-reviewer", "payloadSha256": "panel-sha"}],
    )


def followup_documented_trigger(tmp_path):
    return write_session(
        tmp_path,
        name="followup-documented-trigger",
        state={
            "findings": [
                {
                    "id": "I-documented",
                    "severity": "Important",
                    "disposition": "out-of-scope",
                    "followUp": {
                        "revisitTrigger": "documented",
                        "classClosure": "none",
                    },
                }
            ]
        },
        journal_lines=[_dispatch_observed_journal_row("code-reviewer", "panel-sha")],
        envelopes=[{"seat": "code-reviewer", "payloadSha256": "panel-sha"}],
    )
