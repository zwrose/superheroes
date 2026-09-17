"""Producer for round_certification session fixtures — driver test tree only.

Every checked-in fixture journal row is built through ``round_driver._journal_revision_fields``
and every envelope through the production envelope writer helpers in this module.
"""
import hashlib
import json
import os
import shutil
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import record_paths
import round_certification as RC
import round_driver as RD
import round_records as RR

GENERATED_ROOT = os.path.join(_HERE, "fixtures", "round_certification_generated")
META_FILE = "meta.json"
STATE_FILE = "loop-state.json"
JOURNAL_FILE = "driver-journal.jsonl"
HEAD_CONTENT_BLOBS_FILE = "head-content-blobs.json"
SESSION_ID = "test-session-001"
HEAD_SHA = "a" * 40
RECORDED_AT = "2026-01-01T00:00:00"
PANEL_PHASE = RC.PANEL_PHASE
AUDIT_PHASE = "dispatch-audits"
SIXTEEN_AUDIT_SEATS = tuple("audit-target-%02d" % i for i in range(16))
ANCHOR_SHA = "feb91032a2cb2106f089a25063b8178527ae4359f5412ccf549e9d2f98f28ce9"


def _slot_nonce(seat, phase, attempt, occurrence=0):
    return "nonce-%s-%s-a%d-o%d" % (seat, phase, attempt, occurrence)


def _binding_fields(nonce):
    return {
        "source": "runner",
        "runnerNonce": nonce,
        "recordDigest": "d" * 64,
        "resultDigest": "e" * 64,
        "resultKind": "findings",
    }


def _observation_fields(*, read="engaged"):
    return {
        "read": read,
        "source": "runner",
        "telemetry": "tool-calls",
        "stdoutBytes": 10,
        "wallSeconds": 1.0,
        "tokens": None,
        "toolCalls": None,
    }


def _execution_evidence(binding, *, read="engaged"):
    return {**binding, "observation": _observation_fields(read=read)}


def production_hand_landed_envelope(seat, payload, *, phase=PANEL_PHASE, attempt=0,
                                    occurrence=0, evidence=None):
    if evidence is None:
        evidence = _execution_evidence(
            _binding_fields(_slot_nonce(seat, phase, attempt, occurrence)))
    envelope = {
        "schema": RR.SEAT_RESULT_SCHEMA_V2,
        "session": SESSION_ID,
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
        "recordedAt": RECORDED_AT,
        "executionEvidence": evidence,
    }
    if occurrence:
        envelope["occurrence"] = occurrence
    envelope["envelopeSha256"] = RR.envelope_sha256(payload, evidence)
    return envelope


def production_dispatch_observed_envelope(seat, payload, *, phase=PANEL_PHASE, attempt=0,
                                            occurrence=0, payload_sha=None, read="engaged",
                                            binding=None):
    if binding is None:
        binding = _binding_fields(_slot_nonce(seat, phase, attempt, occurrence))
    if payload_sha is None:
        payload_sha = RR.payload_sha256(payload)
    evidence = _execution_evidence(binding, read=read)
    envelope = {
        "schema": RR.SEAT_RESULT_SCHEMA_V2,
        "session": SESSION_ID,
        "round": 1,
        "phase": phase,
        "seat": seat,
        "attempt": attempt,
        "vendor": "codex",
        "model": "gpt-5.6-sol",
        "payload": payload,
        "payloadSha256": payload_sha,
        "provenance": RC.PROVENANCE_DISPATCH_OBSERVED,
        "recordedAt": RECORDED_AT,
        "dispatchRef": ANCHOR_SHA,
        "orderSha256": ANCHOR_SHA,
        "manifestSha256": ANCHOR_SHA,
        "executionEvidence": evidence,
    }
    if occurrence:
        envelope["occurrence"] = occurrence
    envelope["envelopeSha256"] = RR.envelope_sha256(payload, evidence)
    return envelope


def production_recorded_journal_row(envelope, *, seat, phase=PANEL_PHASE, attempt=0,
                                    occurrence=0, provenance, payload_sha=None, head_sha=None,
                                    extra=None):
    if payload_sha is None:
        payload_sha = envelope.get("payloadSha256")
    row = {
        "cmd": "record-result",
        "outcome": "recorded",
        "phase": phase,
        "round": 1,
        "attempt": attempt,
        "seat": seat,
        "occurrence": occurrence,
        "provenance": provenance,
        "payloadSha256": payload_sha,
        "recordIdentity": {
            "phase": phase,
            "seat": seat,
            "occurrence": occurrence,
            "attempt": attempt,
        },
    }
    if head_sha is not None:
        row["headSha"] = head_sha
    if extra:
        row.update(extra)
    row.update(RD._journal_revision_fields(envelope))
    return row


def _minimal_terminal_state():
    return {
        "schemaVersion": 5,
        "config": {
            "fixerVendor": "claude",
            "baseGuard": RC.BASE_GUARD_CHECKED,
            "headSha": HEAD_SHA,
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
                "disposition": "refuted",
                "dispositionReceipt": {"headSha": HEAD_SHA, "verifyResult": "pass"},
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


def _head_content_blobs_for_findings(findings, head=HEAD_SHA):
    fix_commits = []
    files = {}
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        if finding.get("disposition") != "fixed":
            continue
        path = finding.get("file")
        if not isinstance(path, str) or not path:
            continue
        fix_commits.append({"headSha": head, "path": path, "present": True})
        files[path] = "fix present\n"
    if not fix_commits:
        return None
    return {"headSha": head, "files": files, "fixCommits": fix_commits}


def _write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, sort_keys=True)


def _write_session(output_dir, *, state=None, meta=None, journal_lines=None, envelopes=None,
                   head_content_blobs=None, extra_files=None):
    os.makedirs(output_dir, exist_ok=True)
    meta_obj = {"sessionId": SESSION_ID, "headSha": HEAD_SHA}
    if meta:
        meta_obj.update(meta)
    _write_json(os.path.join(output_dir, META_FILE), meta_obj)
    state_obj = _minimal_terminal_state()
    if state:
        state_obj.update(state)
    _write_json(os.path.join(output_dir, STATE_FILE), state_obj)
    lines = journal_lines if journal_lines is not None else []
    with open(os.path.join(output_dir, JOURNAL_FILE), "w", encoding="utf-8") as fh:
        for row in lines:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    for spec in envelopes or []:
        seat = spec["seat"]
        rnd = spec.get("round", 1)
        phase = spec.get("phase", PANEL_PHASE)
        attempt = spec.get("attempt", 0)
        occurrence = spec.get("occurrence", 0)
        envelope = spec.get("envelope")
        if envelope is None:
            payload = spec.get("payload") or {"findings": []}
            if spec.get("provenance") == RC.PROVENANCE_HAND_LANDED:
                envelope = production_hand_landed_envelope(
                    seat, payload, phase=phase, attempt=attempt, occurrence=occurrence,
                    evidence=spec.get("executionEvidence"))
            else:
                envelope = production_dispatch_observed_envelope(
                    seat, payload, phase=phase, attempt=attempt, occurrence=occurrence,
                    payload_sha=spec.get("payloadSha256"), read=spec.get("read", "engaged"))
        if spec.get("payloadSha256") is not None:
            envelope["payloadSha256"] = spec["payloadSha256"]
        path = record_paths.store_path(output_dir, rnd, phase,
                                       record_paths.storage_key(seat, occurrence), attempt)
        _write_json(path, envelope)
    if head_content_blobs is not None:
        _write_json(os.path.join(output_dir, HEAD_CONTENT_BLOBS_FILE), head_content_blobs)
    elif state_obj.get("findings"):
        blobs = _head_content_blobs_for_findings(state_obj["findings"])
        if blobs is not None:
            _write_json(os.path.join(output_dir, HEAD_CONTENT_BLOBS_FILE), blobs)
    for rel_path, content in (extra_files or {}).items():
        path = os.path.join(output_dir, rel_path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if isinstance(content, dict):
            _write_json(path, content)
        else:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(content)


def _default_dispatch_row(seat, payload_sha, **kw):
    payload = {"findings": []}
    envelope = production_dispatch_observed_envelope(
        seat, payload, payload_sha=payload_sha, **kw)
    return production_recorded_journal_row(
        envelope, seat=seat, phase=kw.get("phase", PANEL_PHASE),
        attempt=kw.get("attempt", 0), occurrence=kw.get("occurrence", 0),
        provenance=RC.PROVENANCE_DISPATCH_OBSERVED, payload_sha=payload_sha,
        head_sha=kw.get("head_sha"))


def build_converged_single_round():
    payload = {"findings": []}
    envelope = production_dispatch_observed_envelope("code-reviewer", payload)
    payload_sha = envelope["payloadSha256"]
    return {
        "state": {
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
        "journal_lines": [
            production_recorded_journal_row(
                envelope, seat="code-reviewer", provenance=RC.PROVENANCE_DISPATCH_OBSERVED,
                payload_sha=payload_sha),
        ],
        "envelopes": [{"seat": "code-reviewer", "envelope": envelope}],
    }


def build_multi_round_fix():
    payload = {"findings": []}
    envelope = production_dispatch_observed_envelope("code-reviewer", payload)
    payload_sha = envelope["payloadSha256"]
    row = production_recorded_journal_row(
        envelope, seat="code-reviewer", provenance=RC.PROVENANCE_DISPATCH_OBSERVED,
        payload_sha=payload_sha)
    return {
        "state": {
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
        "journal_lines": [row],
        "envelopes": [{"seat": "code-reviewer", "envelope": envelope}],
    }


def build_disclosure_channels():
    spec = build_converged_single_round()
    spec["state"]["rounds"] = {
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
    return spec


def build_skipped_blockers():
    spec = build_converged_single_round()
    spec["state"]["_skippedBlockers"] = [
        {
            "id": "B1",
            "title": "tradeoff blocker",
            "severity": "Important",
            "file": "b.py",
            "line": 2,
            "reason": "owner accepted risk",
        }
    ]
    return spec


def build_seat_map_degradations():
    spec = build_converged_single_round()
    spec["state"].update({
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
            "shapeDrivers": [],
        },
    })
    return spec


def build_policy_and_base():
    spec = build_converged_single_round()
    spec["meta"] = {"mode": "branch", "headSha": HEAD_SHA}
    spec["state"]["config"] = {
        "fixerVendor": "claude",
        "baseGuard": RC.BASE_GUARD_CHECKED,
        "headSha": HEAD_SHA,
        "baseRef": HEAD_SHA,
        "baseBranch": "main",
        "baseFetch": "fetched",
        "baseRepo": "origin",
        "repoRoot": "/tmp/repo",
    }
    spec["state"]["_policyApplied"] = [
        {
            "source": "gate-policy",
            "phase": "dispatch-judgment",
            "detail": "pre-authorized skip",
        }
    ]
    return spec


def build_capped_terminal():
    payload = {"findings": []}
    envelope = production_dispatch_observed_envelope("code-reviewer", payload)
    payload_sha = envelope["payloadSha256"]
    return {
        "state": {
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
                {"round": 1, "kind": "capped-with-open-critical", "detail": "open findings remain"}
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
        "journal_lines": [
            production_recorded_journal_row(
                envelope, seat="code-reviewer", provenance=RC.PROVENANCE_DISPATCH_OBSERVED,
                payload_sha=payload_sha),
        ],
        "envelopes": [{"seat": "code-reviewer", "envelope": envelope}],
    }


def build_halted_terminal():
    payload = {"findings": []}
    envelope = production_dispatch_observed_envelope("code-reviewer", payload)
    payload_sha = envelope["payloadSha256"]
    return {
        "state": {
            "terminal": "halted",
            "decisions": [{"round": 1, "kind": "verify-fail", "detail": "verify gate failed"}],
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
        "journal_lines": [
            production_recorded_journal_row(
                envelope, seat="code-reviewer", provenance=RC.PROVENANCE_DISPATCH_OBSERVED,
                payload_sha=payload_sha),
        ],
        "envelopes": [{"seat": "code-reviewer", "envelope": envelope}],
    }


def build_case01_recovered_seat():
    payload = {"findings": []}
    recovered_sha = RR.payload_sha256(payload)
    envelope = production_dispatch_observed_envelope(
        "code-reviewer", payload, attempt=1, payload_sha=recovered_sha)
    return {
        "journal_lines": [
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
            production_recorded_journal_row(
                envelope, seat="code-reviewer", attempt=1,
                provenance=RC.PROVENANCE_DISPATCH_OBSERVED, payload_sha=recovered_sha),
        ],
        "envelopes": [{"seat": "code-reviewer", "attempt": 1, "envelope": envelope}],
    }


def build_case02_unrecovered_seat():
    return {
        "journal_lines": [
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
        "envelopes": [],
    }


def build_case03_reverted_fix():
    payload = {"findings": []}
    verify_sha = RR.payload_sha256(payload)
    envelope = production_dispatch_observed_envelope(
        "code-reviewer", payload, payload_sha=verify_sha)
    return {
        "state": {
            "findings": [
                {
                    "id": "F-fix",
                    "file": "src/guard.py",
                    "line": 12,
                    "title": "missing bounds guard",
                    "severity": "Important",
                    "disposition": "fixed",
                    "dispositionReceipt": {"headSha": HEAD_SHA, "verifyResult": "pass"},
                }
            ]
        },
        "journal_lines": [
            production_recorded_journal_row(
                envelope, seat="code-reviewer", provenance=RC.PROVENANCE_DISPATCH_OBSERVED,
                payload_sha=verify_sha),
        ],
        "envelopes": [{"seat": "code-reviewer", "envelope": envelope}],
        "head_content_blobs": {
            "headSha": HEAD_SHA,
            "files": {"src/guard.py": "# fix landed then reverted on the same head\npass\n"},
            "fixCommits": [
                {"headSha": HEAD_SHA, "path": "src/guard.py", "present": True},
                {"headSha": HEAD_SHA, "path": "src/guard.py", "present": False},
            ],
        },
    }


def build_case04_stale_cited_head():
    stale = "b" * 40
    payload = {"findings": []}
    envelope = production_dispatch_observed_envelope("code-reviewer", payload)
    panel_sha = envelope["payloadSha256"]
    return {
        "meta": {"headSha": HEAD_SHA},
        "journal_lines": [
            production_recorded_journal_row(
                envelope, seat="code-reviewer", provenance=RC.PROVENANCE_DISPATCH_OBSERVED,
                payload_sha=panel_sha, head_sha=stale),
        ],
        "envelopes": [{"seat": "code-reviewer", "envelope": envelope}],
    }


def build_case05_critical_out_of_scope():
    payload = {"findings": []}
    envelope = production_dispatch_observed_envelope("code-reviewer", payload)
    panel_sha = envelope["payloadSha256"]
    return {
        "state": {
            "findings": [
                {
                    "id": "C-oos",
                    "severity": "Critical",
                    "disposition": "out-of-scope",
                    "followUp": {"revisitTrigger": "milestone M2", "classClosure": "none"},
                }
            ]
        },
        "journal_lines": [
            production_recorded_journal_row(
                envelope, seat="code-reviewer", provenance=RC.PROVENANCE_DISPATCH_OBSERVED,
                payload_sha=panel_sha),
        ],
        "envelopes": [{"seat": "code-reviewer", "envelope": envelope}],
    }


def build_case05_critical_skipped():
    payload = {"findings": []}
    envelope = production_dispatch_observed_envelope("code-reviewer", payload)
    panel_sha = envelope["payloadSha256"]
    return {
        "state": {
            "findings": [
                {"id": "C-skip", "severity": "Critical", "disposition": "skipped"}
            ]
        },
        "journal_lines": [
            production_recorded_journal_row(
                envelope, seat="code-reviewer", provenance=RC.PROVENANCE_DISPATCH_OBSERVED,
                payload_sha=panel_sha),
        ],
        "envelopes": [{"seat": "code-reviewer", "envelope": envelope}],
    }


def build_case06_mixed_panel():
    dispatch_payload = {"findings": []}
    dispatch_sha = RR.payload_sha256(dispatch_payload)
    dispatch_envelope = production_dispatch_observed_envelope(
        "code-reviewer", dispatch_payload, payload_sha=dispatch_sha)
    hand_payload = {"findings": []}
    hand_evidence = _execution_evidence(
        _binding_fields(_slot_nonce("security-reviewer", PANEL_PHASE, 0)))
    hand_envelope = production_hand_landed_envelope(
        "security-reviewer", hand_payload, evidence=hand_evidence)
    hand_sha = hand_envelope["payloadSha256"]
    return {
        "state": {
            "certification": {
                "shape": "full-panel-confirmed",
                "fullPanel": True,
                "independence": "independent",
                "base": "fetched",
                "pluginVersionSkew": "not-checked",
                "shapeDrivers": [],
            }
        },
        "journal_lines": [
            production_recorded_journal_row(
                dispatch_envelope, seat="code-reviewer",
                provenance=RC.PROVENANCE_DISPATCH_OBSERVED, payload_sha=dispatch_sha),
            production_recorded_journal_row(
                hand_envelope, seat="security-reviewer",
                provenance=RC.PROVENANCE_HAND_LANDED, payload_sha=hand_sha),
        ],
        "envelopes": [
            {"seat": "code-reviewer", "envelope": dispatch_envelope},
            {"seat": "security-reviewer", "envelope": hand_envelope},
        ],
    }


def build_specimen_must_certify_sixteen_seat_audit():
    journal_lines = []
    envelope_specs = []
    for seat in SIXTEEN_AUDIT_SEATS:
        payload = {"findings": [{"id": seat, "severity": "Minor", "title": "audit ok"}]}
        evidence = _execution_evidence(_binding_fields(_slot_nonce(seat, AUDIT_PHASE, 0)))
        envelope = production_hand_landed_envelope(
            seat, payload, phase=AUDIT_PHASE, evidence=evidence)
        journal_lines.append(
            production_recorded_journal_row(
                envelope, seat=seat, phase=AUDIT_PHASE,
                provenance=RC.PROVENANCE_HAND_LANDED,
                payload_sha=envelope["payloadSha256"]))
        envelope_specs.append(
            {"seat": seat, "phase": AUDIT_PHASE, "envelope": envelope})
    return {
        "state": {
            "certification": {
                "shape": "full-panel-confirmed",
                "fullPanel": True,
                "independence": "independent",
                "base": "fetched",
                "pluginVersionSkew": "not-checked",
                "shapeDrivers": [],
            }
        },
        "journal_lines": journal_lines,
        "envelopes": envelope_specs,
    }


def build_specimen_refuse_bare_fabricated_findings():
    fabricated_sha = "fabricated-sha"
    payload = {"findings": []}
    envelope = production_hand_landed_envelope("code-reviewer", payload)
    envelope["payloadSha256"] = fabricated_sha
    return {
        "journal_lines": [
            production_recorded_journal_row(
                envelope, seat="code-reviewer", provenance=RC.PROVENANCE_HAND_LANDED,
                payload_sha=fabricated_sha),
        ],
        "envelopes": [],
        "extra_files": {
            "findings-code.json": {
                "findings": [
                    {
                        "id": "fabricated-001",
                        "severity": "Important",
                        "title": "never executed",
                    }
                ]
            }
        },
    }


def build_specimen_refuse_fabricated_envelope_audited_chain():
    payload = {
        "findings": [
            {
                "id": "fabricated-002",
                "severity": "Important",
                "title": "authored but never executed",
            }
        ]
    }
    evidence = _execution_evidence(_binding_fields(_slot_nonce("code-reviewer", PANEL_PHASE, 0)))
    envelope = production_hand_landed_envelope("code-reviewer", payload, evidence=evidence)
    return {
        "state": {"certification": {"shape": "full-panel-confirmed", "fullPanel": True}},
        "journal_lines": [
            production_recorded_journal_row(
                envelope, seat="code-reviewer", provenance=RC.PROVENANCE_HAND_LANDED,
                payload_sha=envelope["payloadSha256"]),
        ],
        "envelopes": [{"seat": "code-reviewer", "envelope": envelope}],
    }


def build_specimen_refuse_caller_supplied_execution_evidence():
    payload = {"findings": []}
    evidence = _execution_evidence(_binding_fields(_slot_nonce("code-reviewer", PANEL_PHASE, 0)))
    evidence = dict(evidence)
    evidence["source"] = "/tmp/caller-minted-evidence.json"
    envelope = production_hand_landed_envelope("code-reviewer", payload, evidence=evidence)
    return {
        "journal_lines": [
            production_recorded_journal_row(
                envelope, seat="code-reviewer", provenance=RC.PROVENANCE_HAND_LANDED,
                payload_sha=envelope["payloadSha256"]),
        ],
        "envelopes": [{"seat": "code-reviewer", "envelope": envelope}],
    }


def build_base_guard_not_checked():
    payload = {"findings": []}
    envelope = production_dispatch_observed_envelope("code-reviewer", payload)
    panel_sha = envelope["payloadSha256"]
    return {
        "state": {
            "config": {
                "fixerVendor": "claude",
                "baseGuard": "not-checked",
                "headSha": HEAD_SHA,
            }
        },
        "journal_lines": [
            production_recorded_journal_row(
                envelope, seat="code-reviewer", provenance=RC.PROVENANCE_DISPATCH_OBSERVED,
                payload_sha=panel_sha),
        ],
        "envelopes": [{"seat": "code-reviewer", "envelope": envelope}],
    }


def build_followup_missing_class_closure():
    payload = {"findings": []}
    envelope = production_dispatch_observed_envelope("code-reviewer", payload)
    panel_sha = envelope["payloadSha256"]
    return {
        "state": {
            "findings": [
                {
                    "id": "I-missing-closure",
                    "severity": "Important",
                    "disposition": "out-of-scope",
                    "followUp": {"revisitTrigger": "2026-12-01"},
                }
            ]
        },
        "journal_lines": [
            production_recorded_journal_row(
                envelope, seat="code-reviewer", provenance=RC.PROVENANCE_DISPATCH_OBSERVED,
                payload_sha=panel_sha),
        ],
        "envelopes": [{"seat": "code-reviewer", "envelope": envelope}],
    }


def build_followup_class_closure_none():
    payload = {"findings": []}
    envelope = production_dispatch_observed_envelope("code-reviewer", payload)
    panel_sha = envelope["payloadSha256"]
    return {
        "state": {
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
        "journal_lines": [
            production_recorded_journal_row(
                envelope, seat="code-reviewer", provenance=RC.PROVENANCE_DISPATCH_OBSERVED,
                payload_sha=panel_sha),
        ],
        "envelopes": [{"seat": "code-reviewer", "envelope": envelope}],
    }


def build_followup_no_revisit_trigger():
    payload = {"findings": []}
    envelope = production_dispatch_observed_envelope("code-reviewer", payload)
    panel_sha = envelope["payloadSha256"]
    return {
        "state": {
            "findings": [
                {
                    "id": "I-no-trigger",
                    "severity": "Important",
                    "disposition": "out-of-scope",
                    "followUp": {"classClosure": "tracked in issue-42"},
                }
            ]
        },
        "journal_lines": [
            production_recorded_journal_row(
                envelope, seat="code-reviewer", provenance=RC.PROVENANCE_DISPATCH_OBSERVED,
                payload_sha=panel_sha),
        ],
        "envelopes": [{"seat": "code-reviewer", "envelope": envelope}],
    }


def build_followup_documented_trigger():
    payload = {"findings": []}
    envelope = production_dispatch_observed_envelope("code-reviewer", payload)
    panel_sha = envelope["payloadSha256"]
    return {
        "state": {
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
        "journal_lines": [
            production_recorded_journal_row(
                envelope, seat="code-reviewer", provenance=RC.PROVENANCE_DISPATCH_OBSERVED,
                payload_sha=panel_sha),
        ],
        "envelopes": [{"seat": "code-reviewer", "envelope": envelope}],
    }


FIXTURE_BUILDERS = {
    "converged-single-round": build_converged_single_round,
    "multi-round-fix": build_multi_round_fix,
    "disclosure-channels": build_disclosure_channels,
    "skipped-blockers": build_skipped_blockers,
    "seat-map-degradations": build_seat_map_degradations,
    "policy-and-base": build_policy_and_base,
    "capped-terminal": build_capped_terminal,
    "halted-terminal": build_halted_terminal,
    "case-01-recovered-seat": build_case01_recovered_seat,
    "case-02-unrecovered-seat": build_case02_unrecovered_seat,
    "case-03-reverted-fix": build_case03_reverted_fix,
    "case-04-stale-head": build_case04_stale_cited_head,
    "case-05-critical-oos": build_case05_critical_out_of_scope,
    "case-05-critical-skipped": build_case05_critical_skipped,
    "case-06-mixed-panel": build_case06_mixed_panel,
    "specimen-must-certify-audit": build_specimen_must_certify_sixteen_seat_audit,
    "specimen-refuse-bare-findings": build_specimen_refuse_bare_fabricated_findings,
    "specimen-refuse-fabricated-envelope": build_specimen_refuse_fabricated_envelope_audited_chain,
    "specimen-refuse-caller-evidence": build_specimen_refuse_caller_supplied_execution_evidence,
    "base-guard-not-checked": build_base_guard_not_checked,
    "followup-missing-class-closure": build_followup_missing_class_closure,
    "followup-class-closure-none": build_followup_class_closure_none,
    "followup-no-revisit-trigger": build_followup_no_revisit_trigger,
    "followup-documented-trigger": build_followup_documented_trigger,
}


def regenerate_fixture(name, output_root=GENERATED_ROOT):
    builder = FIXTURE_BUILDERS.get(name)
    if builder is None:
        raise KeyError("unknown fixture %r" % name)
    spec = builder()
    out_dir = os.path.join(output_root, name)
    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)
    _write_session(out_dir, **spec)
    return out_dir


def regenerate_all(output_root=GENERATED_ROOT):
    if os.path.exists(output_root):
        shutil.rmtree(output_root)
    os.makedirs(output_root, exist_ok=True)
    for name in sorted(FIXTURE_BUILDERS):
        regenerate_fixture(name, output_root=output_root)
    manifest = {"fixtures": sorted(FIXTURE_BUILDERS), "generator": os.path.basename(__file__)}
    _write_json(os.path.join(output_root, "manifest.json"), manifest)
    return output_root


def _fixture_tree_digest(root):
    digest = hashlib.sha256()
    for dirpath, _dirnames, filenames in os.walk(root):
        for filename in sorted(filenames):
            path = os.path.join(dirpath, filename)
            rel = os.path.relpath(path, root)
            digest.update(rel.encode("utf-8"))
            digest.update(b"\0")
            with open(path, "rb") as fh:
                digest.update(fh.read())
            digest.update(b"\0")
    return digest.hexdigest()


if __name__ == "__main__":
    regenerate_all()
    print("regenerated %d fixtures under %s" % (len(FIXTURE_BUILDERS), GENERATED_ROOT))
