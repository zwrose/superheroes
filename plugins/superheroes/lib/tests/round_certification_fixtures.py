"""Shared fixture helpers for round_certification tests — test tree only, no driver imports."""
import json
import os
import shutil

import record_paths
import round_certification as RC
import round_records as RR

GENERATED_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "fixtures", "round_certification_generated")
HEAD_SHA = "a" * 40
ANCHOR_SHA = "feb91032a2cb2106f089a25063b8178527ae4359f5412ccf549e9d2f98f28ce9"
DEFAULT_PANEL_PAYLOAD = {"findings": []}
DEFAULT_PANEL_PAYLOAD_SHA = RR.payload_sha256(DEFAULT_PANEL_PAYLOAD)
AUDIT_PHASE = "dispatch-audits"
SIXTEEN_AUDIT_SEATS = tuple("audit-target-%02d" % i for i in range(16))

META_FILE = "meta.json"
STATE_FILE = "loop-state.json"
JOURNAL_FILE = "driver-journal.jsonl"
HEAD_CONTENT_BLOBS_FILE = "head-content-blobs.json"
PANEL_PHASE = RC.PANEL_PHASE

MUST_REFUSE_FIXTURES = []

_FAITHFUL_CALLER_MODULES = frozenset(
    (
        "round_certification_fixtures",
        "test_round_certification_parity",
    )
)


def must_refuse_fixture(**expect):
    """Register a fixture builder whose refusal class/artifact six_cases asserts."""

    def decorate(fn):
        MUST_REFUSE_FIXTURES.append((fn.__name__, fn, expect))
        return fn

    return decorate


def _load_generated(name, tmp_path, session_name=None):
    src = os.path.join(GENERATED_ROOT, name)
    if not os.path.isdir(src):
        raise FileNotFoundError(
            "generated fixture missing: %s (regenerate with generate_round_certification_fixtures.py)"
            % src)
    dest_name = session_name or name
    session_dir = os.path.join(str(tmp_path), dest_name)
    if os.path.exists(session_dir):
        shutil.rmtree(session_dir)
    shutil.copytree(src, session_dir)
    return session_dir


def _caller_wants_faithful_session(explicit):
    if explicit is not None:
        return explicit
    import inspect
    frame = inspect.currentframe()
    if frame is None or frame.f_back is None or frame.f_back.f_back is None:
        return False
    module = frame.f_back.f_back.f_globals.get("__name__", "")
    return module in _FAITHFUL_CALLER_MODULES


def write_session(
    tmp_path,
    *,
    name="session",
    state=None,
    journal_lines=None,
    meta=None,
    envelopes=None,
    faithful_session=None,
):
    """Ad-hoc session writer for driverless tests — not used for the generated parity/six-case set."""
    faithful = _caller_wants_faithful_session(faithful_session)
    session_dir = str(tmp_path / name)
    os.makedirs(session_dir, exist_ok=True)
    meta_obj = {"sessionId": "test-session-001", "headSha": HEAD_SHA}
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
    for spec in envelopes if envelopes is not None else [
        {"seat": "code-reviewer", "payloadSha256": DEFAULT_PANEL_PAYLOAD_SHA}
    ]:
        _write_envelope(session_dir, spec)
    if faithful:
        head = meta_obj.get("headSha") or (state_obj.get("config") or {}).get("headSha") or HEAD_SHA
        blobs_path = os.path.join(session_dir, HEAD_CONTENT_BLOBS_FILE)
        if not os.path.exists(blobs_path):
            blobs = _head_content_blobs_for_findings(state_obj.get("findings") or [], head)
            if blobs is not None:
                _write_head_content_blobs(session_dir, blobs)
    return session_dir


def _minimal_terminal_state():
    head = HEAD_SHA
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
                "disposition": "refuted",
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


def _slot_nonce(seat, phase, attempt, occurrence=0):
    return "nonce-%s-%s-a%d-o%d" % (seat, phase, attempt, occurrence)


def _ad_hoc_envelope(seat, payload, spec):
    phase = spec.get("phase", PANEL_PHASE)
    attempt = spec.get("attempt", 0)
    occurrence = spec.get("occurrence", 0)
    provenance = spec.get("provenance", RC.PROVENANCE_DISPATCH_OBSERVED)
    evidence = spec.get("executionEvidence")
    if evidence is None:
        evidence = _execution_evidence(
            _binding_fields(_slot_nonce(seat, phase, attempt, occurrence)))
    envelope = {
        "schema": RR.SEAT_RESULT_SCHEMA_V2,
        "session": "test-session-001",
        "round": spec.get("round", 1),
        "phase": phase,
        "seat": seat,
        "attempt": attempt,
        "vendor": "codex",
        "model": "gpt-5.6-sol",
        "payload": payload,
        "payloadSha256": spec.get("payloadSha256") or RR.payload_sha256(payload),
        "provenance": provenance,
        "executionEvidence": evidence,
    }
    if provenance == RC.PROVENANCE_HAND_LANDED:
        envelope["manifestSha256"] = ANCHOR_SHA
        envelope["orderSha256"] = ANCHOR_SHA
    if occurrence:
        envelope["occurrence"] = occurrence
    envelope["envelopeSha256"] = RR.envelope_sha256(payload, evidence)
    return envelope


def _write_envelope(session_dir, spec):
    rnd = spec.get("round", 1)
    phase = spec.get("phase", PANEL_PHASE)
    seat = spec["seat"]
    attempt = spec.get("attempt", 0)
    occurrence = spec.get("occurrence", 0)
    path = record_paths.store_path(session_dir, rnd, phase,
                                   record_paths.storage_key(seat, occurrence), attempt)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if spec.get("envelope") is not None:
        envelope = spec["envelope"]
    else:
        payload = spec.get("payload") or {"findings": []}
        envelope = _ad_hoc_envelope(seat, payload, spec)
    if spec.get("payloadSha256") is not None:
        envelope["payloadSha256"] = spec["payloadSha256"]
        envelope["envelopeSha256"] = RR.envelope_sha256(
            envelope.get("payload"), envelope.get("executionEvidence"))
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(envelope, fh, sort_keys=True)


def _default_journal_row():
    payload_sha = DEFAULT_PANEL_PAYLOAD_SHA
    envelope = _ad_hoc_envelope("code-reviewer", DEFAULT_PANEL_PAYLOAD,
                                {"payloadSha256": payload_sha})
    evidence = envelope["executionEvidence"]
    return {
        "cmd": "record-result",
        "outcome": "recorded",
        "phase": PANEL_PHASE,
        "round": 1,
        "attempt": 0,
        "seat": "code-reviewer",
        "occurrence": 0,
        "provenance": RC.PROVENANCE_DISPATCH_OBSERVED,
        "payloadSha256": payload_sha,
        "executionEvidence": evidence,
        "recordIdentity": {
            "phase": PANEL_PHASE,
            "seat": "code-reviewer",
            "occurrence": 0,
            "attempt": 0,
        },
    }


def _head_content_blobs_for_findings(findings, head):
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


def _write_head_content_blobs(session_dir, blobs):
    path = os.path.join(session_dir, HEAD_CONTENT_BLOBS_FILE)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(blobs, fh, sort_keys=True)


def parity_converged_single_round(tmp_path):
    return _load_generated("converged-single-round", tmp_path, session_name="converged-single")


def parity_multi_round_fix(tmp_path):
    return _load_generated("multi-round-fix", tmp_path, session_name="multi-fix")


def parity_disclosure_channels(tmp_path):
    return _load_generated("disclosure-channels", tmp_path, session_name="disclosures")


def parity_skipped_blockers(tmp_path):
    return _load_generated("skipped-blockers", tmp_path, session_name="skipped-blockers")


def parity_seat_map_degradations(tmp_path):
    return _load_generated("seat-map-degradations", tmp_path, session_name="seat-map-degraded")


def parity_policy_and_base(tmp_path):
    return _load_generated("policy-and-base", tmp_path, session_name="policy-base")


def parity_capped_terminal(tmp_path):
    return _load_generated("capped-terminal", tmp_path, session_name="capped")


def parity_halted_terminal(tmp_path):
    return _load_generated("halted-terminal", tmp_path, session_name="halted")


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


def case01_recovered_seat(tmp_path):
    return _load_generated("case-01-recovered-seat", tmp_path)


@must_refuse_fixture(class_in=("unrun-review", "unfetched-findings"), artifact_required=True)
def case02_unrecovered_seat(tmp_path):
    return _load_generated("case-02-unrecovered-seat", tmp_path)


@must_refuse_fixture(class_="disposition-without-receipt", artifact="F-fix")
def case03_reverted_fix(tmp_path):
    return _load_generated("case-03-reverted-fix", tmp_path)


@must_refuse_fixture(
    class_="unrun-review",
    artifact="code-reviewer",
    binding_failure="execution-evidence-stale-head",
)
def case04_stale_cited_head(tmp_path):
    return _load_generated("case-04-stale-head", tmp_path)


@must_refuse_fixture(class_="disposition-without-receipt", artifact="C-oos")
def case05_critical_out_of_scope(tmp_path):
    return _load_generated("case-05-critical-oos", tmp_path)


@must_refuse_fixture(class_="disposition-without-receipt", artifact="C-skip")
def case05_critical_skipped(tmp_path):
    return _load_generated("case-05-critical-skipped", tmp_path)


def case06_mixed_panel(tmp_path):
    return _load_generated("case-06-mixed-panel", tmp_path)


def specimen_must_certify_sixteen_seat_audit(tmp_path):
    return _load_generated("specimen-must-certify-audit", tmp_path)


@must_refuse_fixture(class_in=("unrun-review", "unfetched-findings"), artifact_required=True)
def specimen_refuse_bare_fabricated_findings(tmp_path):
    return _load_generated("specimen-refuse-bare-findings", tmp_path)


def specimen_refuse_fabricated_envelope_audited_chain(tmp_path):
    return _load_generated("specimen-refuse-fabricated-envelope", tmp_path)


@must_refuse_fixture(class_in=("unrun-review", "unfetched-findings"), artifact_required=True)
def specimen_refuse_caller_supplied_execution_evidence(tmp_path):
    return _load_generated("specimen-refuse-caller-evidence", tmp_path)


@must_refuse_fixture(
    class_="disposition-without-receipt",
    binding_failure="base-guard-not-checked",
)
def base_guard_not_checked_session(tmp_path):
    return _load_generated("base-guard-not-checked", tmp_path)


@must_refuse_fixture(
    class_="disposition-without-receipt",
    artifact="I-missing-closure",
    binding_failure="missing-class-closure",
)
def followup_missing_class_closure(tmp_path):
    return _load_generated("followup-missing-class-closure", tmp_path)


def followup_class_closure_none(tmp_path):
    return _load_generated("followup-class-closure-none", tmp_path)


@must_refuse_fixture(
    class_="disposition-without-receipt",
    artifact="I-no-trigger",
    binding_failure="missing-revisit-trigger",
)
def followup_no_revisit_trigger(tmp_path):
    return _load_generated("followup-no-revisit-trigger", tmp_path)


@must_refuse_fixture(class_="disposition-without-receipt", artifact="I-documented")
def followup_documented_trigger(tmp_path):
    return _load_generated("followup-documented-trigger", tmp_path)
