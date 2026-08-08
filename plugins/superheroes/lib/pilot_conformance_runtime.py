"""Headless conformance runtime exercises for pilot wave, reclaim, and mint (C10).

Drives in-repo pilot surfaces without live apps, browsers, or network so a
conformance report can cite exercise receipts instead of intentions.
"""
import os
import shutil
import stat
import sys
import tempfile
import zipfile

import pilot_appctl
import pilot_artifacts
import pilot_conformance
import pilot_contract
import pilot_journal
import pilot_mint
import pilot_reclaim
import pilot_wave
import store

REASON_INPUTS_MISSING = "conformance-runtime-inputs-missing"
REASON_INPUTS_MALFORMED = "conformance-runtime-inputs-malformed"
REASON_SLOTS_DIR_INVALID = "conformance-runtime-slots-dir-invalid"
REASON_EXPECTATION_UNMET = "conformance-runtime-expectation-unmet"
REASON_SWEEP_WARNINGS_EMPTY = "conformance-runtime-sweep-warnings-empty"
REASON_GATE_OFF_UNVERIFIED = "conformance-runtime-gate-off-unverified"

_WAVE_SURFACES = [
    "pilot_appctl.assert_unique_endpoints",
    "pilot_appctl.resolve_invocation",
    "pilot_wave.admit_work",
    "pilot_wave.assert_destructive_allowed",
    "pilot_wave.validate_step_result",
    "pilot_wave.wave_anchor",
    "pilot_wave.wave_phase",
]

_MINT_SURFACES = [
    "pilot_mint.gate_off_receipt",
    "pilot_mint.run_gate_off_test",
]

_RECLAIM_SURFACES = ["pilot_reclaim.sweep"]

_ARTIFACT_SURFACES = ["pilot_artifacts.retain", "pilot_artifacts.sweep"]

_WAVE_LAUNCHED_AT = "2026-08-02T12:00:00Z"
_WAVE_DEADLINE_SECONDS = 10
_WAVE_MARGIN_SECONDS = 5
_WAVE_STEP_OBSERVED_AT = "2026-08-02T12:01:00Z"

_QUARANTINE_AT = "2026-08-02T12:00:00Z"
_QUARANTINE_REASON = "stale-occupant"
_DEFAULT_SLOT_REF = "slot-a@1"


def _has_control_char(value):
    return any(ord(ch) < 32 for ch in value)


def _normalize_evidence(text):
    if not isinstance(text, str):
        text = str(text)
    cleaned = "".join(ch for ch in text if ord(ch) >= 32)
    if len(cleaned) > pilot_conformance.EVIDENCE_MAX_LEN:
        return cleaned[:pilot_conformance.EVIDENCE_MAX_LEN]
    return cleaned


def _truncate_warning_value(value):
    if not isinstance(value, str):
        value = str(value)
    cleaned = "".join(ch for ch in value if ord(ch) >= 32)
    if len(cleaned) > pilot_conformance.WARNING_VALUE_MAX_LEN:
        return cleaned[:pilot_conformance.WARNING_VALUE_MAX_LEN]
    return cleaned


def _skipped(exercise, surfaces, reason, evidence, exercised_at):
    return pilot_conformance.exercise_record(
        exercise=exercise,
        surfaces=surfaces,
        result=pilot_conformance.RESULT_SKIPPED,
        reason=reason,
        evidence=_normalize_evidence(evidence),
        exercised_at=exercised_at,
    )


def _failed(exercise, surfaces, reason, evidence, exercised_at, warnings=None):
    return pilot_conformance.exercise_record(
        exercise=exercise,
        surfaces=surfaces,
        result=pilot_conformance.RESULT_FAIL,
        reason=reason,
        evidence=_normalize_evidence(evidence),
        exercised_at=exercised_at,
        warnings=warnings,
    )


def _passed(exercise, surfaces, evidence, exercised_at, warnings=None):
    return pilot_conformance.exercise_record(
        exercise=exercise,
        surfaces=surfaces,
        result=pilot_conformance.RESULT_PASS,
        reason=None,
        evidence=_normalize_evidence(evidence),
        exercised_at=exercised_at,
        warnings=warnings,
    )


def _exercise_key(inputs, key):
    # bite-axis: coverage honesty — absent or malformed exercise inputs skip rather than pass.
    if not isinstance(inputs, dict):
        return None, REASON_INPUTS_MISSING
    if key not in inputs:
        return None, REASON_INPUTS_MISSING
    value = inputs[key]
    if not isinstance(value, dict):
        return None, REASON_INPUTS_MALFORMED
    return value, None


def _valid_slots_dir(path):
    return isinstance(path, str) and bool(path) and os.path.isdir(path)


def _writable_slots_dir(path):
    return _valid_slots_dir(path) and os.access(path, os.W_OK)


def _wave_receipt(step, slot_ref):
    return {
        "step": step,
        "slotRef": slot_ref,
        "observedAt": _WAVE_STEP_OBSERVED_AT,
        "evidence": "stopped",
    }


def _check_wave_deadline_math():
    anchor_result = pilot_wave.wave_anchor(
        launched_at=_WAVE_LAUNCHED_AT,
        deadline_seconds=_WAVE_DEADLINE_SECONDS,
        margin_seconds=_WAVE_MARGIN_SECONDS,
        monotonic=lambda: 0.0,
    )
    if not anchor_result["ok"]:
        return REASON_EXPECTATION_UNMET
    anchor = anchor_result["anchor"]

    running = pilot_wave.wave_phase(anchor, monotonic=lambda: 9.999)
    if not running["ok"] or running["phase"] != pilot_wave.PHASE_RUNNING:
        return REASON_EXPECTATION_UNMET

    winding = pilot_wave.wave_phase(anchor, monotonic=lambda: 10.0)
    if not winding["ok"] or winding["phase"] != pilot_wave.PHASE_WINDING_DOWN:
        return REASON_EXPECTATION_UNMET

    expired = pilot_wave.wave_phase(anchor, monotonic=lambda: 15.0)
    if not expired["ok"] or expired["phase"] != pilot_wave.PHASE_EXPIRED:
        return REASON_EXPECTATION_UNMET
    return None


def _check_wave_admission(anchor):
    admitted = pilot_wave.admit_work(anchor, monotonic=lambda: 5.0)
    if not admitted["ok"]:
        return REASON_EXPECTATION_UNMET
    refused = pilot_wave.admit_work(anchor, monotonic=lambda: 20.0)
    if refused["ok"]:
        return REASON_EXPECTATION_UNMET
    return None


def _check_wave_step_validation(slot_ref):
    good = pilot_wave.validate_step_result(
        {
            "outcome": pilot_journal.OUTCOME_APPLIED,
            "receipt": _wave_receipt(pilot_wave.STEP_APP, slot_ref),
        },
        step=pilot_wave.STEP_APP,
        slot_ref=slot_ref,
    )
    if good["status"] != pilot_wave.STATUS_CONFIRMED:
        return REASON_EXPECTATION_UNMET

    bad = pilot_wave.validate_step_result(
        {"outcome": pilot_journal.OUTCOME_APPLIED, "receipt": None},
        step=pilot_wave.STEP_APP,
        slot_ref=slot_ref,
    )
    if bad["status"] != pilot_wave.STATUS_INDETERMINATE:
        return REASON_EXPECTATION_UNMET
    if bad["reason"] != pilot_wave.REASON_STEP_RECEIPT_MISSING:
        return REASON_EXPECTATION_UNMET
    return None


def _check_wave_destructive_gate():
    allowed = pilot_wave.assert_destructive_allowed(
        pilot_wave.STEP_CLEANUP,
        intent=pilot_wave.INTENT_COMPLETE,
        latched=False,
    )
    if not allowed["ok"]:
        return REASON_EXPECTATION_UNMET

    park_refused = pilot_wave.assert_destructive_allowed(
        pilot_wave.STEP_CLEANUP,
        intent=pilot_wave.INTENT_PARK,
        latched=False,
    )
    if park_refused["ok"]:
        return REASON_EXPECTATION_UNMET
    if park_refused["reason"] != pilot_wave.REASON_PARK_DESTRUCTIVE_REFUSED:
        return REASON_EXPECTATION_UNMET

    latched_refused = pilot_wave.assert_destructive_allowed(
        pilot_wave.STEP_CLEANUP,
        intent=pilot_wave.INTENT_COMPLETE,
        latched=True,
    )
    if latched_refused["ok"]:
        return REASON_EXPECTATION_UNMET
    if latched_refused["reason"] != pilot_wave.REASON_PARK_DESTRUCTIVE_REFUSED:
        return REASON_EXPECTATION_UNMET
    return None


def _check_appctl_fencing():
    distinct = pilot_appctl.assert_unique_endpoints([
        {"slotRef": "slot-a@1", "host": "127.0.0.1", "port": 3000},
        {"slotRef": "slot-b@1", "host": "127.0.0.1", "port": 3001},
    ])
    if not distinct["ok"]:
        return REASON_EXPECTATION_UNMET

    # bite-axis: bidirectional refusal — duplicate endpoints must refuse, not only distinct accept.
    duplicate = pilot_appctl.assert_unique_endpoints([
        {"slotRef": "slot-a@1", "host": "localhost", "port": 3000},
        {"slotRef": "slot-b@1", "host": "LOCALHOST.", "port": 3000},
    ])
    if duplicate["ok"]:
        return REASON_EXPECTATION_UNMET
    if duplicate["reason"] != pilot_appctl.REASON_ENDPOINT_DUPLICATE:
        return REASON_EXPECTATION_UNMET
    return None


def _check_appctl_invocation():
    resolved = pilot_appctl.resolve_invocation(
        ["run", "{port}"],
        params={"port": "3000"},
        readiness_url="http://127.0.0.1:{port}/ready",
    )
    if not resolved["ok"]:
        return REASON_EXPECTATION_UNMET

    unresolved = pilot_appctl.resolve_invocation(
        ["echo", "{missing}"],
        params={},
        readiness_url="http://127.0.0.1/ready",
    )
    if unresolved["ok"]:
        return REASON_EXPECTATION_UNMET
    if unresolved["reason"] != pilot_appctl.REASON_PLACEHOLDER_UNRESOLVED:
        return REASON_EXPECTATION_UNMET
    return None


def _occupant():
    return {
        "pid": 12345,
        "processInstance": "inst-abc",
        "livenessSource": "mtime",
        "observedAt": _QUARANTINE_AT,
    }


def _seed_payload_dir(session_root):
    # bite-axis: containment — exercise work stays in a disposable subtree of slots_dir.
    path = os.path.join(session_root, "occupant-payload")
    os.makedirs(path, exist_ok=True)
    marker = os.path.join(path, "work.txt")
    with open(marker, "w", encoding="utf-8") as handle:
        handle.write("payload")
    return path


def _remove_work_dir(work_dir):
    if work_dir and os.path.isdir(work_dir):
        shutil.rmtree(work_dir, ignore_errors=True)


def _fold_warned(warned):
    folded = []
    for entry in warned:
        entry_name = entry.get("entryName", "")
        reason = entry.get("reason")
        if reason is None:
            reason = ""
        folded.append({
            "entryName": _truncate_warning_value(entry_name),
            "reason": _truncate_warning_value(reason),
        })
    return folded


def _receipt_well_formed(record, envelope, exercised_at):
    if not isinstance(record, dict):
        return False
    if record.get("kind") != "mint-gate-off":
        return False
    if record.get("exercisedAt") != exercised_at:
        return False
    if record.get("declarationDigest") != pilot_contract.declaration_digest(envelope):
        return False
    receipt = record.get("receipt")
    if not isinstance(receipt, dict):
        return False
    if receipt.get("result") not in ("pass", "fail"):
        return False
    evidence = receipt.get("evidence")
    return isinstance(evidence, str) and bool(evidence)


@pilot_conformance.register("wave-headless", surfaces=_WAVE_SURFACES)
def wave_headless_exercise(*, inputs, now):
    wave_inputs, skip_reason = _exercise_key(inputs, "wave")
    if skip_reason is not None:
        return _skipped(
            "wave-headless",
            _WAVE_SURFACES,
            skip_reason,
            "wave inputs absent or malformed",
            now,
        )

    slots_dir = wave_inputs.get("slots_dir")
    slot_ref = wave_inputs.get("slot_ref")
    if not _valid_slots_dir(slots_dir):
        return _skipped(
            "wave-headless",
            _WAVE_SURFACES,
            REASON_SLOTS_DIR_INVALID,
            "wave slots_dir missing or not a directory",
            now,
        )
    if not isinstance(slot_ref, str) or not slot_ref:
        return _skipped(
            "wave-headless",
            _WAVE_SURFACES,
            REASON_INPUTS_MALFORMED,
            "wave slot_ref missing or wrong type",
            now,
        )

    anchor_result = pilot_wave.wave_anchor(
        launched_at=_WAVE_LAUNCHED_AT,
        deadline_seconds=_WAVE_DEADLINE_SECONDS,
        margin_seconds=_WAVE_MARGIN_SECONDS,
        monotonic=lambda: 0.0,
    )
    if not anchor_result["ok"]:
        return _failed(
            "wave-headless",
            _WAVE_SURFACES,
            REASON_EXPECTATION_UNMET,
            "wave anchor could not be built",
            now,
        )
    anchor = anchor_result["anchor"]

    checks = (
        _check_wave_deadline_math,
        lambda: _check_wave_admission(anchor),
        lambda: _check_wave_step_validation(slot_ref),
        _check_wave_destructive_gate,
        _check_appctl_fencing,
        _check_appctl_invocation,
    )
    for check in checks:
        reason = check()
        if reason is not None:
            return _failed(
                "wave-headless",
                _WAVE_SURFACES,
                reason,
                "wave-headless expectation unmet",
                now,
            )

    return _passed(
        "wave-headless",
        _WAVE_SURFACES,
        "wave deadline, admission, teardown validation, fencing, and invocation exercised",
        now,
    )


@pilot_conformance.register("reclaim-sweep", surfaces=_RECLAIM_SURFACES)
def reclaim_sweep_exercise(*, inputs, now):
    reclaim_inputs, skip_reason = _exercise_key(inputs, "reclaim")
    if skip_reason is not None:
        return _skipped(
            "reclaim-sweep",
            _RECLAIM_SURFACES,
            skip_reason,
            "reclaim inputs absent or malformed",
            now,
        )

    slots_dir = reclaim_inputs.get("slots_dir")
    if not _writable_slots_dir(slots_dir):
        return _skipped(
            "reclaim-sweep",
            _RECLAIM_SURFACES,
            REASON_SLOTS_DIR_INVALID,
            "reclaim slots_dir missing, not a directory, or not writable",
            now,
        )

    session_root = None
    try:
        session_root = tempfile.mkdtemp(dir=slots_dir, prefix="conformance-reclaim-")
        nested_store = os.path.join(session_root, "slot-store")
        os.makedirs(nested_store)
        source_path = _seed_payload_dir(session_root)
        slot_ref = reclaim_inputs.get("slot_ref", _DEFAULT_SLOT_REF)
        if not isinstance(slot_ref, str) or not slot_ref:
            slot_ref = _DEFAULT_SLOT_REF

        quarantine = pilot_reclaim.quarantine_entry(
            nested_store,
            source_path,
            slot_ref=slot_ref,
            reason=_QUARANTINE_REASON,
            occupant=_occupant(),
            now=_QUARANTINE_AT,
        )
        if not quarantine["ok"]:
            return _failed(
                "reclaim-sweep",
                _RECLAIM_SURFACES,
                quarantine["reason"],
                "reclaim quarantine seed failed",
                now,
            )

        sweep = pilot_reclaim.sweep(nested_store, now=now)
        if not sweep["ok"]:
            return _failed(
                "reclaim-sweep",
                _RECLAIM_SURFACES,
                sweep["reason"],
                "reclaim sweep refused",
                now,
            )

        entry_name = quarantine["entryName"]
        warned = sweep.get("warned") or []
        retained = sweep.get("retained") or []

        # bite-axis: sweep fold honesty — past-grace quarantine must warn; empty warned is a fail.
        if not warned:
            return _failed(
                "reclaim-sweep",
                _RECLAIM_SURFACES,
                REASON_SWEEP_WARNINGS_EMPTY,
                "reclaim sweep produced no warnings for seeded past-grace entry",
                now,
            )

        warned_names = {entry.get("entryName") for entry in warned}
        if entry_name not in warned_names:
            return _failed(
                "reclaim-sweep",
                _RECLAIM_SURFACES,
                REASON_EXPECTATION_UNMET,
                "seeded quarantine entry missing from sweep warnings",
                now,
            )

        retained_names = {entry.get("entryName") for entry in retained}
        if entry_name not in retained_names:
            return _failed(
                "reclaim-sweep",
                _RECLAIM_SURFACES,
                REASON_EXPECTATION_UNMET,
                "seeded quarantine entry not retained by sweep",
                now,
            )

        warnings = _fold_warned(warned)

        return _passed(
            "reclaim-sweep",
            _RECLAIM_SURFACES,
            "reclaim sweep warned on past-grace quarantine and warnings folded",
            now,
            warnings=warnings,
        )
    finally:
        _remove_work_dir(session_root)


@pilot_conformance.register("artifact-store", surfaces=_ARTIFACT_SURFACES)
def artifact_store_exercise(*, inputs, now):
    """Exercise retain + sweep inside a disposable artifact subtree."""
    pa = pilot_artifacts
    if not isinstance(inputs, dict):
        return _skipped(
            "artifact-store",
            _ARTIFACT_SURFACES,
            pa.REASON_MATERIAL_INVALID,
            "inputs missing or malformed",
            now,
        )

    artifacts = inputs.get("artifacts")
    if not isinstance(artifacts, dict):
        return _skipped(
            "artifact-store",
            _ARTIFACT_SURFACES,
            pa.REASON_MATERIAL_INVALID,
            "artifacts input missing or malformed",
            now,
        )

    artifacts_dir = artifacts.get("artifacts_dir")
    branch = artifacts.get("branch")
    slot = artifacts.get("slot")
    material = artifacts.get("material")
    if (
        not isinstance(artifacts_dir, str)
        or not isinstance(branch, str)
        or not isinstance(slot, str)
        or not isinstance(material, (list, tuple))
        or not material
    ):
        return _skipped(
            "artifact-store",
            _ARTIFACT_SURFACES,
            pa.REASON_MATERIAL_INVALID,
            "artifacts fields missing or malformed",
            now,
        )

    work_dir = None
    try:
        work_dir = tempfile.mkdtemp(prefix="conformance-artifacts-")
        held = 0
        first_fail = None

        clean = pa.retain(
            work_dir,
            branch=branch,
            slot=slot,
            artifact_class=pa.CLASS_STEP_LOG,
            payload_text="step ok",
            material=material,
            now=now,
        )
        if clean.get("ok"):
            payload_path = clean["path"]
            sidecar_path = clean["sidecar"]
            if (
                os.path.isfile(payload_path)
                and os.path.isfile(sidecar_path)
                and stat.S_IMODE(os.stat(payload_path).st_mode) == pa._FILE_MODE
                and stat.S_IMODE(os.stat(sidecar_path).st_mode) == pa._FILE_MODE
            ):
                held += 1
            else:
                first_fail = first_fail or pa.REASON_WRITE_FAILED
        else:
            first_fail = first_fail or clean.get("reason")

        dirty_before = 0
        class_dir = os.path.join(
            work_dir, store.artifact_key(branch, slot), pa.CLASS_STEP_LOG
        )
        if os.path.isdir(class_dir):
            dirty_before = sum(
                1 for name in os.listdir(class_dir)
                if not name.endswith(pa.SIDECAR_SUFFIX)
                and os.path.isfile(os.path.join(class_dir, name))
            )
        dirty = pa.retain(
            work_dir,
            branch=branch,
            slot=slot,
            artifact_class=pa.CLASS_STEP_LOG,
            payload_text="failed connecting to %s" % material[0],
            material=material,
            now=now,
        )
        dirty_after = 0
        if os.path.isdir(class_dir):
            dirty_after = sum(
                1 for name in os.listdir(class_dir)
                if not name.endswith(pa.SIDECAR_SUFFIX)
                and os.path.isfile(os.path.join(class_dir, name))
            )
        if (
            not dirty.get("ok")
            and dirty.get("reason") == pa.REASON_REDACTION_UNESTABLISHED
            and dirty_after == dirty_before
        ):
            held += 1
        else:
            first_fail = first_fail or dirty.get("reason") or pa.REASON_REDACTION_UNESTABLISHED

        trace_fd, trace_zip = tempfile.mkstemp(suffix=".zip")
        os.close(trace_fd)
        try:
            with zipfile.ZipFile(trace_zip, "w") as zf:
                zf.writestr("log.txt", "trace line")
            trace_refused = pa.retain(
                work_dir,
                branch=branch,
                slot=slot,
                artifact_class=pa.CLASS_TRACE,
                payload_path=trace_zip,
                material=material,
                now=now,
                opted_in=False,
            )
        finally:
            try:
                os.unlink(trace_zip)
            except OSError:
                pass
        if not trace_refused.get("ok") and trace_refused.get("reason") == pa.REASON_CLASS_NOT_OPTED_IN:
            held += 1
        else:
            first_fail = first_fail or trace_refused.get("reason") or pa.REASON_CLASS_NOT_OPTED_IN

        short_now = now
        short = pa.retain(
            work_dir,
            branch=branch,
            slot=slot,
            artifact_class=pa.CLASS_STEP_LOG,
            payload_text="expires soon",
            material=material,
            now=short_now,
            retention_hours=1,
        )
        if short.get("ok"):
            later = pa._add_hours_iso8601(short_now, 2)
            sweep_out = pa.sweep(work_dir, now=later)
            removed = sweep_out.get("removed", [])
            expired = [
                entry for entry in removed
                if entry.get("reason") == pa.REASON_RETENTION_EXPIRED
                and entry.get("artifactId") == short.get("artifactId")
            ]
            if expired:
                held += 1
            else:
                first_fail = first_fail or pa.REASON_RETENTION_EXPIRED
        else:
            first_fail = first_fail or short.get("reason")

        if held == 4:
            return _passed(
                "artifact-store",
                _ARTIFACT_SURFACES,
                "4/4 expectations held",
                now,
            )

        return _failed(
            "artifact-store",
            _ARTIFACT_SURFACES,
            first_fail or pa.REASON_WRITE_FAILED,
            "%d/4 expectations held" % held,
            now,
        )
    finally:
        if work_dir and os.path.isdir(work_dir):
            shutil.rmtree(work_dir, ignore_errors=True)


@pilot_conformance.register("mint-gate-off", surfaces=_MINT_SURFACES)
def mint_gate_off_exercise(*, inputs, now):
    mint_inputs, skip_reason = _exercise_key(inputs, "mint")
    if skip_reason is not None:
        return _skipped(
            "mint-gate-off",
            _MINT_SURFACES,
            skip_reason,
            "mint inputs absent or malformed",
            now,
        )

    envelope = mint_inputs.get("envelope")
    run_cwd = mint_inputs.get("run_cwd")
    environment = mint_inputs.get("environment")
    if not isinstance(envelope, dict):
        return _skipped(
            "mint-gate-off",
            _MINT_SURFACES,
            REASON_INPUTS_MALFORMED,
            "mint envelope missing or wrong type",
            now,
        )
    if not isinstance(run_cwd, str) or not run_cwd or not os.path.isdir(run_cwd):
        return _skipped(
            "mint-gate-off",
            _MINT_SURFACES,
            REASON_INPUTS_MALFORMED,
            "mint run_cwd missing or not a directory",
            now,
        )
    if not isinstance(environment, dict):
        return _skipped(
            "mint-gate-off",
            _MINT_SURFACES,
            REASON_INPUTS_MALFORMED,
            "mint environment missing or wrong type",
            now,
        )

    run_result = pilot_mint.run_gate_off_test(
        envelope,
        run_cwd=run_cwd,
        environment=environment,
    )
    if not run_result.get("ok"):
        reason = run_result.get("reason")
        if not isinstance(reason, str) or not reason:
            reason = REASON_GATE_OFF_UNVERIFIED
        return _failed(
            "mint-gate-off",
            _MINT_SURFACES,
            reason,
            "mint gate-off run did not pass",
            now,
        )

    # bite-axis: receipt production — runner success alone is insufficient; gate_off_receipt must be well-formed.
    try:
        receipt_record = pilot_mint.gate_off_receipt(
            envelope,
            run_result,
            exercised_at=now,
        )
    except pilot_mint.PilotMintError as exc:
        reason = getattr(exc, "reason", REASON_GATE_OFF_UNVERIFIED)
        return _failed(
            "mint-gate-off",
            _MINT_SURFACES,
            reason,
            "mint gate-off receipt could not be built",
            now,
        )

    if not _receipt_well_formed(receipt_record, envelope, now):
        return _failed(
            "mint-gate-off",
            _MINT_SURFACES,
            REASON_GATE_OFF_UNVERIFIED,
            "mint gate-off receipt failed well-formedness check",
            now,
        )

    return _passed(
        "mint-gate-off",
        _MINT_SURFACES,
        "mint gate-off command exercised and receipt well-formed",
        now,
    )
