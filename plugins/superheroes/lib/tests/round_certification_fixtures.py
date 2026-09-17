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
