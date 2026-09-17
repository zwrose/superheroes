"""Shared fixture helpers for round_certification tests — test tree only, no driver imports."""
import json
import os

import round_certification as RC

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
