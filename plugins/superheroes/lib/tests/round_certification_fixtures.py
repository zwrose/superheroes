"""Shared fixture helpers for round_certification tests — test tree only, no driver imports."""
import base64
import hashlib
import json
import os
import shutil

import record_paths
import round_certification as RC
import round_records as RR
import session_contract

GENERATED_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "fixtures", "round_certification_generated")
HEAD_SHA = "a" * 40
ANCHOR_SHA = "feb91032a2cb2106f089a25063b8178527ae4359f5412ccf549e9d2f98f28ce9"
DEFAULT_PANEL_PAYLOAD = {"findings": []}
DEFAULT_PANEL_PAYLOAD_SHA = RR.payload_sha256(DEFAULT_PANEL_PAYLOAD)
DEFAULT_FINDINGS_RESULT_SHA = RR.payload_sha256(DEFAULT_PANEL_PAYLOAD["findings"])
AUDIT_PHASE = "dispatch-audits"
SCOPED_PHASE = "dispatch-scoped-finder"
SCOPED_SEAT = "scoped-finder"
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
    stamp_certified_head(session_dir)
    return session_dir


def stamp_certified_head(session_dir):
    """Give a converged fixture certificate the head a real driver would have recorded.

    The certification writer binds a converged state's evidence to `certification.certifiedHead`
    and nothing else. Fixtures written before that field existed name their head in the fix-fold
    head, meta, or config; this stamps that head as the certificate's, once, at the shared writers.
    A fixture that sets the key itself (including to None, to model a headless certificate) keeps it."""
    state_path = os.path.join(session_dir, STATE_FILE)
    try:
        with open(state_path, encoding="utf-8") as fh:
            state = json.load(fh)
    except (OSError, ValueError):
        return
    cert = state.get("certification") if isinstance(state, dict) else None
    if state.get("terminal") != "converged" or not isinstance(cert, dict) or "certifiedHead" in cert:
        return
    try:
        with open(os.path.join(session_dir, META_FILE), encoding="utf-8") as fh:
            meta = json.load(fh)
    except (OSError, ValueError):
        meta = {}
    meta = meta if isinstance(meta, dict) else {}
    cfg = state.get("config") if isinstance(state.get("config"), dict) else {}
    key = session_contract.FIX_FOLD_HEAD_KEY
    for head in (meta.get(key), cfg.get(key), meta.get("headSha"), cfg.get("headSha")):
        if isinstance(head, str) and head:
            cert["certifiedHead"] = head
            with open(state_path, "w", encoding="utf-8") as fh:
                json.dump(state, fh, sort_keys=True)
            return


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
    _normalize_refuted_findings(state_obj)
    with open(os.path.join(session_dir, STATE_FILE), "w", encoding="utf-8") as fh:
        json.dump(state_obj, fh, sort_keys=True)
    lines = journal_lines if journal_lines is not None else [_default_journal_row()]
    payload_lookup = _payload_lookup_from_envelope_specs(envelopes)
    with open(os.path.join(session_dir, JOURNAL_FILE), "w", encoding="utf-8") as fh:
        for row in lines:
            fh.write(
                json.dumps(_normalize_journal_row(row, payload_lookup), sort_keys=True)
                + "\n"
            )
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
    stamp_certified_head(session_dir)
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
                "refutedReason": "Reviewer confirmed the cited behavior is intentional.",
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


_LEGACY_TYPED_RESULT_DIGEST = "e" * 64


def _binding_fields(nonce="test-nonce", *, result_digest=None):
    digest = (
        result_digest
        if isinstance(result_digest, str) and result_digest
        else DEFAULT_FINDINGS_RESULT_SHA
    )
    return {
        "source": "runner",
        "runnerNonce": nonce,
        "recordDigest": "d" * 64,
        "resultDigest": digest,
        "resultKind": "findings",
    }


def _dispatch_journal_with_binding(
    seat="code-reviewer",
    payload_sha=DEFAULT_PANEL_PAYLOAD_SHA,
    *,
    nonce="test-nonce",
    attempt=0,
    head_sha=HEAD_SHA,
    read="engaged",
):
    evidence = {
        "read": read,
        "source": "runner",
        "telemetry": "tool-calls",
        "stdoutBytes": 10,
        "wallSeconds": 1.0,
        "toolCalls": 1,
        "runKind": session_contract.run_kind_for_phase(PANEL_PHASE),
        **_binding_fields(nonce, result_digest=DEFAULT_FINDINGS_RESULT_SHA),
    }
    row = {
        "cmd": "record-result",
        "outcome": "recorded",
        "phase": PANEL_PHASE,
        "round": 1,
        "attempt": attempt,
        "seat": seat,
        "occurrence": 0,
        "provenance": RC.PROVENANCE_DISPATCH_OBSERVED,
        "payloadSha256": payload_sha,
        "executionEvidence": evidence,
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


def _hand_landed_binding_journal_row(seat, payload_sha, evidence, *, attempt=0):
    return {
        "cmd": "record-result",
        "outcome": "recorded",
        "phase": PANEL_PHASE,
        "round": 1,
        "attempt": attempt,
        "seat": seat,
        "provenance": RC.PROVENANCE_HAND_LANDED,
        "payloadSha256": payload_sha,
        "executionEvidence": {
            field: evidence[field]
            for field in RC.EXECUTION_EVIDENCE_BINDING_FIELDS
        },
        "recordIdentity": {
            "phase": PANEL_PHASE,
            "seat": seat,
            "occurrence": 0,
            "attempt": attempt,
        },
    }


_FIX_PRESENT_BYTES = b"fix present\n"


def _head_content_read_row(path, content_bytes, head=HEAD_SHA):
    digest = hashlib.sha256(content_bytes).hexdigest()
    return {
        "headSha": head,
        "path": path,
        "contentDigest": digest,
        "bytes": len(content_bytes),
        "readAt": "2026-01-01T00:00:00Z",
        "source": "git-show",
        "readError": None,
    }, digest


def _observation_fields(*, read="engaged", tool_calls=1):
    return {
        "read": read,
        "source": "runner",
        "telemetry": "tool-calls",
        "stdoutBytes": 10,
        "wallSeconds": 1.0,
        "tokens": None,
        "toolCalls": tool_calls,
    }


def _execution_evidence(binding, *, read="engaged", phase=PANEL_PHASE):
    return {
        **binding,
        "runKind": session_contract.run_kind_for_phase(phase),
        "observation": _observation_fields(read=read),
    }


def _slot_nonce(seat, phase, attempt, occurrence=0):
    return "nonce-%s-%s-a%d-o%d" % (seat, phase, attempt, occurrence)


def _normalize_legacy_result_digest(evidence, payload):
    if not isinstance(evidence, dict) or not isinstance(payload, dict):
        return evidence
    if evidence.get("resultDigest") != _LEGACY_TYPED_RESULT_DIGEST:
        return evidence
    result_kind = evidence.get("resultKind")
    if not isinstance(result_kind, str) or result_kind not in payload:
        return evidence
    normalized = dict(evidence)
    normalized["resultDigest"] = RR.payload_sha256(payload[result_kind])
    return normalized


def _normalize_refuted_findings(state):
    if not isinstance(state, dict):
        return
    findings = state.get("findings")
    if not isinstance(findings, list):
        return
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        if finding.get("disposition") != "refuted":
            continue
        reason = finding.get("refutedReason")
        if isinstance(reason, str) and reason.strip():
            continue
        receipt = finding.get("dispositionReceipt")
        if isinstance(receipt, str) and receipt.strip():
            continue
        if isinstance(receipt, dict):
            if any(
                isinstance(key, str) and key.startswith("fixContent")
                for key in receipt
            ):
                continue
            if any(
                isinstance(receipt.get(key), str) and receipt.get(key).strip()
                for key in ("reason", "refutedReason", "text")
            ):
                continue
            finding["refutedReason"] = (
                "Reviewer confirmed the cited behavior is intentional."
            )


def _normalize_dispatch_journal_row(row):
    if not isinstance(row, dict):
        return row
    if row.get("provenance") != RC.PROVENANCE_DISPATCH_OBSERVED:
        return row
    if row.get("outcome") != "recorded":
        return row
    evidence = row.get("executionEvidence")
    if not isinstance(evidence, dict):
        return row
    tool_calls = evidence.get("toolCalls")
    if isinstance(tool_calls, int) and tool_calls >= 1:
        return row
    observation = evidence.get("observation")
    if isinstance(observation, dict):
        obs_tool_calls = observation.get("toolCalls")
        if isinstance(obs_tool_calls, int) and obs_tool_calls >= 1:
            return row
    normalized = dict(row)
    normalized_evidence = dict(evidence)
    if isinstance(observation, dict):
        normalized_obs = dict(observation)
        if "tokens" not in normalized_obs:
            normalized_obs["tokens"] = None
        normalized_obs["toolCalls"] = 1
        normalized_evidence["observation"] = normalized_obs
    else:
        normalized_evidence["toolCalls"] = 1
    normalized["executionEvidence"] = normalized_evidence
    return normalized


def _normalize_journal_row(row, payload_lookup=None):
    row = _normalize_dispatch_journal_row(row)
    evidence = row.get("executionEvidence")
    if not isinstance(evidence, dict):
        return row
    payload = None
    payload_sha = row.get("payloadSha256")
    if isinstance(payload_sha, str) and payload_lookup:
        payload = payload_lookup.get(payload_sha)
    if payload is None and payload_sha == DEFAULT_PANEL_PAYLOAD_SHA:
        payload = DEFAULT_PANEL_PAYLOAD
    result_kind = evidence.get("resultKind")
    if payload is None and result_kind == "findings":
        payload = {"findings": []}
    if not isinstance(payload, dict):
        return row
    normalized_evidence = _normalize_legacy_result_digest(evidence, payload)
    if normalized_evidence is evidence:
        return row
    normalized = dict(row)
    normalized["executionEvidence"] = normalized_evidence
    return normalized


def _payload_lookup_from_envelope_specs(envelopes):
    lookup = {}
    for spec in envelopes or []:
        payload = spec.get("payload")
        payload_sha = spec.get("payloadSha256")
        if isinstance(payload, dict) and isinstance(payload_sha, str):
            lookup[payload_sha] = payload
    return lookup


def _ad_hoc_envelope(seat, payload, spec):
    phase = spec.get("phase", PANEL_PHASE)
    attempt = spec.get("attempt", 0)
    occurrence = spec.get("occurrence", 0)
    provenance = spec.get("provenance", RC.PROVENANCE_DISPATCH_OBSERVED)
    evidence = spec.get("executionEvidence")
    payload_sha = spec.get("payloadSha256") or RR.payload_sha256(payload)
    result_digest = RR.payload_sha256(payload.get("findings", []))
    if evidence is None:
        binding = _binding_fields(
            _slot_nonce(seat, phase, attempt, occurrence),
            result_digest=result_digest,
        )
        evidence = _execution_evidence(binding, phase=phase)
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
        "payloadSha256": payload_sha,
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
    payload_obj = envelope.get("payload")
    if isinstance(payload_obj, dict):
        evidence = envelope.get("executionEvidence")
        if isinstance(evidence, dict):
            envelope = dict(envelope)
            envelope["executionEvidence"] = _normalize_legacy_result_digest(
                evidence, payload_obj
            )
            envelope["envelopeSha256"] = RR.envelope_sha256(
                envelope.get("payload"), envelope.get("executionEvidence"))
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
        "headSha": HEAD_SHA,
        "executionEvidence": evidence,
        "recordIdentity": {
            "phase": PANEL_PHASE,
            "seat": "code-reviewer",
            "occurrence": 0,
            "attempt": 0,
        },
    }


def _head_content_blobs_for_findings(findings, head=HEAD_SHA):
    reads = []
    files = {}
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        if finding.get("disposition") != "fixed":
            continue
        path = finding.get("file")
        if not isinstance(path, str) or not path:
            continue
        row, _digest = _head_content_read_row(path, _FIX_PRESENT_BYTES, head)
        reads.append(row)
        files[path] = base64.b64encode(_FIX_PRESENT_BYTES).decode("ascii")
    if not reads:
        return None
    return {
        "schema": session_contract.HEAD_CONTENT_BLOBS_SCHEMA,
        "headSha": head,
        "files": files,
        "reads": reads,
    }


def _write_head_content_blobs(session_dir, blobs):
    path = os.path.join(session_dir, HEAD_CONTENT_BLOBS_FILE)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(blobs, fh, sort_keys=True)


def write_certifiable_session(tmp_path, **kwargs):
    """Session with binding telemetry and head-content evidence for fixed findings."""
    state = kwargs.get("state")
    if state is None:
        state = {}
    elif not isinstance(state, dict):
        state = {}
    kwargs = dict(kwargs)
    kwargs["state"] = state
    if kwargs.get("journal_lines") is None:
        kwargs["journal_lines"] = [_dispatch_journal_with_binding()]
    session_dir = write_session(tmp_path, **kwargs)
    findings = (state.get("findings") if state else None) or []
    blobs = _head_content_blobs_for_findings(findings)
    if blobs is None:
        blobs = _head_content_blobs_for_findings(
            [
                {
                    "id": "F1",
                    "file": "a.py",
                    "disposition": "fixed",
                }
            ]
        )
    _write_head_content_blobs(session_dir, blobs)
    return session_dir


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


def _orders_manifest_for_seat(seat, *, rnd=1, attempt=0, phase=PANEL_PHASE):
    return {
        "schema": "orders-manifest/1",
        "session": "test-session-001",
        "round": rnd,
        "phase": phase,
        "attempt": attempt,
        "orders": "not-emitted",
        "seats": {
            seat: {
                "storeKey": seat,
                "seat": seat,
                "occurrence": 0,
                "vendor": "codex",
                "model": "gpt-5.6-sol",
                "engine": "codex",
                "resultContract": "seat-result/2",
                "orderSha256": ANCHOR_SHA,
                "orderPath": "/dev/null",
                "envelopeStubPath": "/dev/null",
            },
        },
    }


def _write_orders_manifest(session_dir, manifest):
    path = RC._orders_manifest_path(
        session_dir, manifest["round"], manifest["phase"], manifest["attempt"])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    text = session_contract.canonical(manifest)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return session_contract.sha256_text(text)


def _dispatch_envelope_for(seat, phase, rnd, *, payload=None):
    payload = payload if payload is not None else DEFAULT_PANEL_PAYLOAD
    payload_sha = RR.payload_sha256(payload)
    spec = {
        "seat": seat,
        "phase": phase,
        "round": rnd,
        "payload": payload,
        "payloadSha256": payload_sha,
    }
    return _ad_hoc_envelope(seat, payload, spec)


def _recorded_row_from_envelope(envelope, seat, phase, rnd, *, head_sha, attempt=0):
    row = {
        "cmd": "record-result",
        "outcome": "recorded",
        "phase": phase,
        "round": rnd,
        "attempt": attempt,
        "seat": seat,
        "occurrence": 0,
        "provenance": RC.PROVENANCE_DISPATCH_OBSERVED,
        "payloadSha256": envelope["payloadSha256"],
        "headSha": head_sha,
        "recordIdentity": {
            "phase": phase,
            "seat": seat,
            "occurrence": 0,
            "attempt": attempt,
        },
    }
    row.update(
        RR.recorded_row_fields(envelope, head_sha, RR.CITED_HEAD_SOURCE_ORDER_ANCHOR)
    )
    return row


def _audit_dispatch_envelope(target_id, rnd, ruling="discharged", new_issues=None):
    audit_payload = {
        "id": target_id,
        "ruling": ruling,
        "auditorVendor": "codex",
        "reason": "re-read the fixed hunk; the defect is gone",
    }
    if ruling == "discharged-but-new-issue" and new_issues is not None:
        audit_payload["newIssues"] = new_issues
    payload_sha = session_contract.payload_sha256(audit_payload)
    binding = _binding_fields(
        _slot_nonce(target_id, AUDIT_PHASE, 0),
        result_digest=payload_sha,
    )
    binding["source"] = "codex"
    evidence = _execution_evidence(binding, phase=AUDIT_PHASE)
    evidence["source"] = "codex"
    evidence["resultKind"] = "ruling"
    evidence["resultDigest"] = payload_sha
    observation = evidence.get("observation")
    if isinstance(observation, dict):
        evidence["observation"] = dict(observation, source="codex")
    envelope = {
        "schema": RR.SEAT_RESULT_SCHEMA_V2,
        "session": "test-session-001",
        "round": rnd,
        "phase": AUDIT_PHASE,
        "seat": target_id,
        "attempt": 0,
        "vendor": "codex",
        "model": "gpt-5.6-sol",
        "payload": audit_payload,
        "payloadSha256": payload_sha,
        "provenance": RC.PROVENANCE_DISPATCH_OBSERVED,
        "executionEvidence": evidence,
    }
    envelope["envelopeSha256"] = RR.envelope_sha256(audit_payload, evidence)
    return envelope


def _case07_core(tmp_path, *, include_audit=True, include_scoped=True):
    """Audited-chain certification: panel at ancestor head, fix + scoped finder + verify at tip."""
    from session_checkout import _git, make_checkout

    repo = tmp_path / "repo"
    panel_head = make_checkout(repo)
    delta_path = repo / "delta.txt"
    delta_path.write_text("delta\n", encoding="utf-8")
    _git(repo, "add", "delta.txt")
    _git(repo, "commit", "-q", "-m", "certified tip")
    certified_head = _git(repo, "rev-parse", "HEAD").stdout.strip()

    fix_path = "src/guard.py"
    fix_digest = hashlib.sha256(_FIX_PRESENT_BYTES).hexdigest()
    finding = {
        "id": "F-fix",
        "file": fix_path,
        "line": 12,
        "title": "missing bounds guard",
        "severity": "Important",
        "disposition": "fixed",
        "dispositionRound": 2,
        "dispositionReceipt": {
            "headSha": certified_head,
            "verifyResult": "pass",
            "fixContentHeadSha": certified_head,
            "fixContentDigest": fix_digest,
            "fixContentBytes": len(_FIX_PRESENT_BYTES),
        },
    }
    canonical_key = session_contract.finding_identity_key(finding)
    finding[session_contract.FINDING_KEY_FIELD] = canonical_key
    panel_payload = {"findings": []}
    panel_envelope = _dispatch_envelope_for("code-reviewer", PANEL_PHASE, 1, payload=panel_payload)
    audit_target = canonical_key
    audit_envelope = _audit_dispatch_envelope(audit_target, 2) if include_audit else None
    scoped_envelope = (
        _dispatch_envelope_for(SCOPED_SEAT, SCOPED_PHASE, 2) if include_scoped else None
    )

    manifest = _orders_manifest_for_seat("code-reviewer")
    audit_manifest = (
        _orders_manifest_for_seat(canonical_key, rnd=2, attempt=0, phase=AUDIT_PHASE)
        if include_audit
        else None
    )
    orders_row = {
        "cmd": "advance",
        "outcome": "orders-emitted",
        "phase": PANEL_PHASE,
        "round": 1,
        "attempt": 0,
    }
    audit_orders_row = {
        "cmd": "advance",
        "outcome": "orders-emitted",
        "phase": AUDIT_PHASE,
        "round": 2,
        "attempt": 0,
    }

    session_dir = write_session(
        tmp_path,
        name="case07-audited-chain",
        meta={
            "repoRoot": str(repo),
            "headSha": panel_head,
            session_contract.FIX_FOLD_HEAD_KEY: certified_head,
        },
        state={
            "round": 2,
            "config": {
                "fixerVendor": "claude",
                "baseGuard": RC.BASE_GUARD_CHECKED,
                "headSha": panel_head,
                "repoRoot": str(repo),
                "dimensions": ["code-reviewer"],
                session_contract.FIX_FOLD_HEAD_KEY: certified_head,
            },
            "certification": {
                "shape": "full-panel-confirmed",
                "fullPanel": True,
                "independence": "independent",
                "base": "fetched",
                "shapeDrivers": [],
            },
            "findings": [finding],
            "rounds": {
                "1": {
                    # Driver: round_driver fix fold _record_round(..., "fixFoldHead") on fixer round r;
                    # disposition lands on audit round r+1 (dispositionRound).
                    "roundKind": "baseline",
                    "seatStatus": {"code-reviewer": "run"},
                    "blockingCount": 1,
                    "verifyResult": "pass",
                    "verifyPasses": [],
                    "verifiedHead": panel_head,
                    "fixFoldHead": certified_head,
                },
                "2": {
                    "roundKind": "fix",
                    "seatStatus": {SCOPED_SEAT: "run"} if include_scoped else {},
                    "blockingCount": 0,
                    "verifyResult": "pass",
                    "verifyPasses": [],
                    "verifiedHead": certified_head,
                    **(
                        {"scopedFinder": "skipped-empty-surface"}
                        if not include_scoped
                        else {}
                    ),
                },
            },
        },
        journal_lines=[
            orders_row,
            _recorded_row_from_envelope(
                panel_envelope, "code-reviewer", PANEL_PHASE, 1, head_sha=panel_head),
            *(
                [audit_orders_row]
                if include_audit
                else []
            ),
            *(
                [
                    _recorded_row_from_envelope(
                        audit_envelope, audit_target, AUDIT_PHASE, 2, head_sha=certified_head),
                ]
                if include_audit and audit_envelope is not None
                else []
            ),
            *(
                [
                    _recorded_row_from_envelope(
                        scoped_envelope, SCOPED_SEAT, SCOPED_PHASE, 2, head_sha=certified_head),
                ]
                if include_scoped and scoped_envelope is not None
                else []
            ),
        ],
        envelopes=[
            {"seat": "code-reviewer", "phase": PANEL_PHASE, "round": 1, "envelope": panel_envelope},
            *(
                [
                    {
                        "seat": audit_target,
                        "phase": AUDIT_PHASE,
                        "round": 2,
                        "envelope": audit_envelope,
                    },
                ]
                if include_audit and audit_envelope is not None
                else []
            ),
            *(
                [
                    {
                        "seat": SCOPED_SEAT,
                        "phase": SCOPED_PHASE,
                        "round": 2,
                        "envelope": scoped_envelope,
                    },
                ]
                if include_scoped and scoped_envelope is not None
                else []
            ),
        ],
        faithful_session=True,
    )
    manifest_sha = _write_orders_manifest(session_dir, manifest)
    orders_row["manifestSha256"] = manifest_sha
    audit_manifest_sha = None
    if audit_manifest is not None:
        audit_manifest_sha = _write_orders_manifest(session_dir, audit_manifest)
        audit_orders_row["manifestSha256"] = audit_manifest_sha
    journal_path = os.path.join(session_dir, JOURNAL_FILE)
    lines = []
    with open(journal_path, encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            if row.get("outcome") == "orders-emitted" and row.get("phase") == PANEL_PHASE:
                row["manifestSha256"] = manifest_sha
            if (
                audit_manifest_sha is not None
                and row.get("outcome") == "orders-emitted"
                and row.get("phase") == AUDIT_PHASE
                and row.get("round") == 2
            ):
                row["manifestSha256"] = audit_manifest_sha
            lines.append(row)
    with open(journal_path, "w", encoding="utf-8") as fh:
        for row in lines:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    blobs = _head_content_blobs_for_findings([finding], certified_head)
    if blobs is not None:
        _write_head_content_blobs(session_dir, blobs)
    return session_dir


def case07_audited_chain(tmp_path):
    return _case07_core(tmp_path, include_audit=True, include_scoped=True)


def two_fix_rounds_rebound_session(tmp_path, *, receipt_mutator=None):
    """Two fix rounds: round-1 receipt re-bound to certified head; round-3 fix at tip."""
    from session_checkout import _git, make_checkout

    repo = tmp_path / "repo"
    panel_head = make_checkout(repo)
    delta_path = repo / "delta.txt"
    delta_path.write_text("delta\n", encoding="utf-8")
    _git(repo, "add", "delta.txt")
    _git(repo, "commit", "-q", "-m", "round-1 fix")
    h1 = _git(repo, "rev-parse", "HEAD").stdout.strip()
    extra_path = repo / "delta2.txt"
    extra_path.write_text("delta2\n", encoding="utf-8")
    _git(repo, "add", "delta2.txt")
    _git(repo, "commit", "-q", "-m", "round-3 fix")
    certified_head = _git(repo, "rev-parse", "HEAD").stdout.strip()

    fix_path = "src/guard.py"
    fix_path2 = "src/leak.py"
    fix_digest = hashlib.sha256(_FIX_PRESENT_BYTES).hexdigest()
    finding1 = {
        "id": "F-fix-1",
        "file": fix_path,
        "line": 12,
        "title": "missing bounds guard",
        "severity": "Important",
        "disposition": "fixed",
        "dispositionRound": 2,
        "dispositionReceipt": {
            "headSha": certified_head,
            "verifyResult": "pass",
            "fixContentHeadSha": h1,
            "fixContentDigest": fix_digest,
            "fixContentBytes": len(_FIX_PRESENT_BYTES),
        },
    }
    finding2 = {
        "id": "F-fix-2",
        "file": fix_path2,
        "line": 4,
        "title": "regression adjacent to fix",
        "severity": "Important",
        "disposition": "fixed",
        "dispositionRound": 4,
        "dispositionReceipt": {
            "headSha": certified_head,
            "verifyResult": "pass",
            "fixContentHeadSha": certified_head,
            "fixContentDigest": fix_digest,
            "fixContentBytes": len(_FIX_PRESENT_BYTES),
        },
    }
    if receipt_mutator is not None:
        receipt_mutator(
            finding1,
            panel_head=panel_head,
            h1=h1,
            certified_head=certified_head,
        )
    key1 = session_contract.finding_identity_key(finding1)
    key2 = session_contract.finding_identity_key(finding2)
    finding1[session_contract.FINDING_KEY_FIELD] = key1
    finding2[session_contract.FINDING_KEY_FIELD] = key2

    panel_payload = {"findings": []}
    panel_envelope = _dispatch_envelope_for("code-reviewer", PANEL_PHASE, 1, payload=panel_payload)
    audit1 = _audit_dispatch_envelope(key1, 2)
    audit2 = _audit_dispatch_envelope(key2, 4)
    scoped2 = _dispatch_envelope_for(SCOPED_SEAT, SCOPED_PHASE, 2)
    scoped3 = _dispatch_envelope_for(SCOPED_SEAT, SCOPED_PHASE, 3)
    scoped4 = _dispatch_envelope_for(SCOPED_SEAT, SCOPED_PHASE, 4)

    manifest = _orders_manifest_for_seat("code-reviewer")
    audit_manifest1 = _orders_manifest_for_seat(key1, rnd=2, attempt=0, phase=AUDIT_PHASE)
    audit_manifest2 = _orders_manifest_for_seat(key2, rnd=4, attempt=0, phase=AUDIT_PHASE)

    journal_lines = [
        {
            "cmd": "advance",
            "outcome": "orders-emitted",
            "phase": PANEL_PHASE,
            "round": 1,
            "attempt": 0,
        },
        _recorded_row_from_envelope(
            panel_envelope, "code-reviewer", PANEL_PHASE, 1, head_sha=panel_head),
        {
            "cmd": "advance",
            "outcome": "orders-emitted",
            "phase": AUDIT_PHASE,
            "round": 2,
            "attempt": 0,
        },
        _recorded_row_from_envelope(audit1, key1, AUDIT_PHASE, 2, head_sha=h1),
        _recorded_row_from_envelope(scoped2, SCOPED_SEAT, SCOPED_PHASE, 2, head_sha=certified_head),
        _recorded_row_from_envelope(scoped3, SCOPED_SEAT, SCOPED_PHASE, 3, head_sha=certified_head),
        {
            "cmd": "advance",
            "outcome": "orders-emitted",
            "phase": AUDIT_PHASE,
            "round": 4,
            "attempt": 0,
        },
        _recorded_row_from_envelope(audit2, key2, AUDIT_PHASE, 4, head_sha=certified_head),
        _recorded_row_from_envelope(scoped4, SCOPED_SEAT, SCOPED_PHASE, 4, head_sha=certified_head),
    ]

    session_dir = write_session(
        tmp_path,
        name="two-fix-rounds-rebound",
        meta={
            "repoRoot": str(repo),
            "headSha": panel_head,
            session_contract.FIX_FOLD_HEAD_KEY: certified_head,
        },
        state={
            "round": 4,
            "config": {
                "fixerVendor": "claude",
                "baseGuard": RC.BASE_GUARD_CHECKED,
                "headSha": panel_head,
                "repoRoot": str(repo),
                "dimensions": ["code-reviewer"],
                session_contract.FIX_FOLD_HEAD_KEY: certified_head,
            },
            "certification": {
                "shape": "full-panel-confirmed",
                "fullPanel": True,
                "independence": "independent",
                "base": "fetched",
                "shapeDrivers": [],
            },
            "findings": [finding1, finding2],
            "rounds": {
                "1": {
                    "roundKind": "baseline",
                    "seatStatus": {"code-reviewer": "run"},
                    "blockingCount": 1,
                    "verifyResult": "pass",
                    "verifyPasses": [],
                    "verifiedHead": h1,
                    "fixFoldHead": h1,
                },
                "2": {
                    "roundKind": "fix",
                    "scopedFinder": "skipped-empty-surface",
                    "verifyResult": "pass",
                    "verifiedHead": certified_head,
                },
                "3": {
                    "roundKind": "fix",
                    "verifyResult": "pass",
                    "verifiedHead": certified_head,
                    "fixFoldHead": certified_head,
                },
                "4": {
                    "roundKind": "fix",
                    "scopedFinder": "skipped-empty-surface",
                    "verifyResult": "pass",
                    "verifiedHead": certified_head,
                },
            },
        },
        journal_lines=journal_lines,
        envelopes=[
            {"seat": "code-reviewer", "phase": PANEL_PHASE, "round": 1, "envelope": panel_envelope},
            {"seat": key1, "phase": AUDIT_PHASE, "round": 2, "envelope": audit1},
            {"seat": SCOPED_SEAT, "phase": SCOPED_PHASE, "round": 2, "envelope": scoped2},
            {"seat": SCOPED_SEAT, "phase": SCOPED_PHASE, "round": 3, "envelope": scoped3},
            {"seat": key2, "phase": AUDIT_PHASE, "round": 4, "envelope": audit2},
            {"seat": SCOPED_SEAT, "phase": SCOPED_PHASE, "round": 4, "envelope": scoped4},
        ],
        faithful_session=True,
    )
    manifest_sha = _write_orders_manifest(session_dir, manifest)
    audit_manifest1_sha = _write_orders_manifest(session_dir, audit_manifest1)
    audit_manifest2_sha = _write_orders_manifest(session_dir, audit_manifest2)
    journal_path = os.path.join(session_dir, JOURNAL_FILE)
    lines = []
    with open(journal_path, encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            if row.get("outcome") == "orders-emitted" and row.get("phase") == PANEL_PHASE:
                row["manifestSha256"] = manifest_sha
            if (
                row.get("outcome") == "orders-emitted"
                and row.get("phase") == AUDIT_PHASE
                and row.get("round") == 2
            ):
                row["manifestSha256"] = audit_manifest1_sha
            if (
                row.get("outcome") == "orders-emitted"
                and row.get("phase") == AUDIT_PHASE
                and row.get("round") == 4
            ):
                row["manifestSha256"] = audit_manifest2_sha
            lines.append(row)
    with open(journal_path, "w", encoding="utf-8") as fh:
        for row in lines:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    blobs = _head_content_blobs_for_findings([finding1, finding2], certified_head)
    if blobs is not None:
        _write_head_content_blobs(session_dir, blobs)
    return session_dir


@must_refuse_fixture(
    class_="unrun-review",
    artifact="code-reviewer",
    binding_failure="execution-evidence-stale-head",
)
def case07_audited_chain_missing_audit(tmp_path):
    return _case07_core(tmp_path, include_audit=False, include_scoped=True)


def case07_audited_chain_skipped_scoped(tmp_path):
    return _case07_core(tmp_path, include_audit=True, include_scoped=False)


def _default_case08_new_issues():
    return [
        {
            "severity": "Important",
            "file": "src/leak.py",
            "line": 4,
            "title": "regression adjacent to fix",
        },
    ]


def _case08_ledger_rows(finding, canonical_key, certified_head, fix_digest, extra_rows=()):
    original = {
        session_contract.FINDING_KEY_FIELD: canonical_key,
        "id": finding["id"],
        "file": finding["file"],
        "line": finding["line"],
        "title": finding["title"],
        "severity": finding["severity"],
        "disposition": "fixed",
        "dispositionRound": 2,
        session_contract.RAISED_ROUND_FIELD: 1,
        session_contract.RAISED_SEQ_FIELD: 1,
        session_contract.DISPOSITION_SEQ_FIELD: 2,
        "dispositionReceipt": dict(finding["dispositionReceipt"]),
    }
    return [original, *extra_rows]


def case08_new_issue_audit(
    tmp_path,
    *,
    new_issues=None,
    ledger_rows=None,
    ruling="discharged-but-new-issue",
    seed_raised_new_issue=False,
):
    """Audited-chain with discharged-but-new-issue fix receipt and ledger-owned dispositions."""
    from session_checkout import _git, make_checkout

    if new_issues is None:
        new_issues = _default_case08_new_issues()
    repo = tmp_path / "repo"
    panel_head = make_checkout(repo)
    delta_path = repo / "delta.txt"
    delta_path.write_text("delta\n", encoding="utf-8")
    _git(repo, "add", "delta.txt")
    _git(repo, "commit", "-q", "-m", "certified tip")
    certified_head = _git(repo, "rev-parse", "HEAD").stdout.strip()

    fix_path = "src/guard.py"
    fix_digest = hashlib.sha256(_FIX_PRESENT_BYTES).hexdigest()
    finding = {
        "id": "F-fix",
        "file": fix_path,
        "line": 12,
        "title": "missing bounds guard",
        "severity": "Important",
        "disposition": "fixed",
        "dispositionRound": 2,
        "dispositionReceipt": {
            "headSha": certified_head,
            "verifyResult": "pass",
            "fixContentHeadSha": certified_head,
            "fixContentDigest": fix_digest,
            "fixContentBytes": len(_FIX_PRESENT_BYTES),
        },
    }
    canonical_key = session_contract.finding_identity_key(finding)
    finding[session_contract.FINDING_KEY_FIELD] = canonical_key
    if ledger_rows is None:
        ledger_rows = _case08_ledger_rows(finding, canonical_key, certified_head, fix_digest)
    if seed_raised_new_issue and ruling == "discharged-but-new-issue":
        seeded = list(ledger_rows)
        for seq, cand in enumerate(new_issues, start=1):
            line = cand["line"]
            if not isinstance(line, int):
                line = int(str(line).strip())
            seeded.append({
                session_contract.FINDING_KEY_FIELD: session_contract.minted_identity_key(cand),
                "file": cand["file"],
                "line": line,
                "title": cand["title"],
                "severity": cand["severity"],
                session_contract.RAISED_ROUND_FIELD: 2,
                session_contract.RAISED_SEQ_FIELD: seq,
            })
        ledger_rows = seeded
    panel_payload = {"findings": []}
    panel_envelope = _dispatch_envelope_for("code-reviewer", PANEL_PHASE, 1, payload=panel_payload)
    audit_target = canonical_key
    audit_envelope = _audit_dispatch_envelope(
        audit_target, 2, ruling=ruling, new_issues=new_issues if ruling == "discharged-but-new-issue" else None)
    scoped_envelope = _dispatch_envelope_for(SCOPED_SEAT, SCOPED_PHASE, 2)

    manifest = _orders_manifest_for_seat("code-reviewer")
    audit_manifest = _orders_manifest_for_seat(canonical_key, rnd=2, attempt=0, phase=AUDIT_PHASE)
    orders_row = {
        "cmd": "advance",
        "outcome": "orders-emitted",
        "phase": PANEL_PHASE,
        "round": 1,
        "attempt": 0,
    }
    audit_orders_row = {
        "cmd": "advance",
        "outcome": "orders-emitted",
        "phase": AUDIT_PHASE,
        "round": 2,
        "attempt": 0,
    }

    session_dir = write_session(
        tmp_path,
        name="case08-new-issue-audit",
        meta={
            "repoRoot": str(repo),
            "headSha": panel_head,
            session_contract.FIX_FOLD_HEAD_KEY: certified_head,
        },
        state={
            "round": 2,
            session_contract.DISPOSITION_LEDGER_OWNER_FIELD: session_contract.DISPOSITION_LEDGER_OWNER_VALUE,
            session_contract.DISPOSITION_LEDGER_KEY: ledger_rows,
            "config": {
                "fixerVendor": "claude",
                "baseGuard": RC.BASE_GUARD_CHECKED,
                "headSha": panel_head,
                "repoRoot": str(repo),
                "dimensions": ["code-reviewer"],
                session_contract.FIX_FOLD_HEAD_KEY: certified_head,
            },
            "certification": {
                "shape": "full-panel-confirmed",
                "fullPanel": True,
                "independence": "independent",
                "base": "fetched",
                "shapeDrivers": [],
            },
            "findings": [],
            "rounds": {
                "1": {
                    "roundKind": "baseline",
                    "seatStatus": {"code-reviewer": "run"},
                    "blockingCount": 1,
                    "verifyResult": "pass",
                    "verifyPasses": [],
                    "verifiedHead": panel_head,
                    "fixFoldHead": certified_head,
                },
                "2": {
                    "roundKind": "fix",
                    "seatStatus": {SCOPED_SEAT: "run"},
                    "blockingCount": 0,
                    "verifyResult": "pass",
                    "verifyPasses": [],
                    "verifiedHead": certified_head,
                },
            },
        },
        journal_lines=[
            orders_row,
            _recorded_row_from_envelope(
                panel_envelope, "code-reviewer", PANEL_PHASE, 1, head_sha=panel_head),
            audit_orders_row,
            _recorded_row_from_envelope(
                audit_envelope, audit_target, AUDIT_PHASE, 2, head_sha=certified_head),
            _recorded_row_from_envelope(
                scoped_envelope, SCOPED_SEAT, SCOPED_PHASE, 2, head_sha=certified_head),
        ],
        envelopes=[
            {"seat": "code-reviewer", "phase": PANEL_PHASE, "round": 1, "envelope": panel_envelope},
            {
                "seat": audit_target,
                "phase": AUDIT_PHASE,
                "round": 2,
                "envelope": audit_envelope,
            },
            {
                "seat": SCOPED_SEAT,
                "phase": SCOPED_PHASE,
                "round": 2,
                "envelope": scoped_envelope,
            },
        ],
        faithful_session=True,
    )
    manifest_sha = _write_orders_manifest(session_dir, manifest)
    orders_row["manifestSha256"] = manifest_sha
    audit_manifest_sha = _write_orders_manifest(session_dir, audit_manifest)
    audit_orders_row["manifestSha256"] = audit_manifest_sha
    journal_path = os.path.join(session_dir, JOURNAL_FILE)
    lines = []
    with open(journal_path, encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            if row.get("outcome") == "orders-emitted" and row.get("phase") == PANEL_PHASE:
                row["manifestSha256"] = manifest_sha
            if (
                row.get("outcome") == "orders-emitted"
                and row.get("phase") == AUDIT_PHASE
                and row.get("round") == 2
            ):
                row["manifestSha256"] = audit_manifest_sha
            lines.append(row)
    with open(journal_path, "w", encoding="utf-8") as fh:
        for row in lines:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    blobs = _head_content_blobs_for_findings([finding], certified_head)
    if blobs is not None:
        _write_head_content_blobs(session_dir, blobs)
    return session_dir


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
