"""Conformance exercise for pilot_cleanup end-to-end containment (C10).

A successful cleanup leader can leave a destructive child running when the command
exits cleanly after detaching a helper; see ``pilot_bounded_run`` for the declared
limit on process-group signalling.
"""
import os
import shutil

import pilot_boundary
import pilot_cleanup
import pilot_conformance
import pilot_contract
import pilot_slot

REASON_INPUTS_MISSING = "conformance-cleanup-inputs-missing"
REASON_INPUTS_MALFORMED = "conformance-cleanup-inputs-malformed"
REASON_RECEIPT_NOT_PASS = "conformance-cleanup-receipt-not-pass"
REASON_REGISTRY_INVALID = "conformance-cleanup-registry-invalid"
REASON_BINDING_FAILED = "conformance-cleanup-binding-failed"
REASON_CONTAINMENT_NOT_RECEIPT = "conformance-cleanup-containment-not-receipt"
REASON_CONTAINMENT_REFUSED = "conformance-cleanup-containment-refused"
REASON_PLAN_NOT_RESURRECT = "conformance-cleanup-plan-not-resurrect"
REASON_PLAN_REFUSED = "conformance-cleanup-plan-refused"
REASON_RUN_CWD_INSIDE_REACH = "conformance-cleanup-run-cwd-inside-reach"

EXERCISE_NAME = "cleanup-end-to-end"
EVIDENCE_PASS = "5/5 steps held; plan produced, not executed"

_SURFACES = [
    "pilot_cleanup.cleanup_effect_receipt",
    "pilot_cleanup.receipt_valid_for",
    "pilot_cleanup.registry_record",
    "pilot_cleanup.resolve_containment",
    "pilot_cleanup.resurrection_plan",
]

_REQUIRED_CLEANUP_KEYS = (
    "policy",
    "pilot_block",
    "slot_ref",
    "reach_roots",
    "run_cwd",
    "cleanup_root",
    "journal_path",
    "observed_identity",
    "identity_provenance",
    "identity_strength",
    "verdict",
    "account",
    "mint_envelope",
)


def _token_reason(reason, fallback):
    if (
        isinstance(reason, str)
        and reason
        and not any(ch.isspace() for ch in reason)
        and len(reason) <= pilot_conformance.REASON_TOKEN_MAX_LEN
    ):
        return reason
    return fallback


def _skipped_record(now, reason=REASON_INPUTS_MISSING):
    return pilot_conformance.exercise_record(
        exercise=EXERCISE_NAME,
        surfaces=list(_SURFACES),
        result=pilot_conformance.RESULT_SKIPPED,
        reason=reason,
        evidence="cleanup inputs absent or malformed",
        exercised_at=now,
    )


def _fail_record(now, reason, *, evidence, warnings=None, fallback=REASON_RECEIPT_NOT_PASS):
    return pilot_conformance.exercise_record(
        exercise=EXERCISE_NAME,
        surfaces=list(_SURFACES),
        result=pilot_conformance.RESULT_FAIL,
        reason=_token_reason(reason, fallback),
        evidence=evidence,
        exercised_at=now,
        warnings=warnings,
    )


def _validate_cleanup_inputs(cleanup):
    if not isinstance(cleanup, dict):
        return False
    for key in _REQUIRED_CLEANUP_KEYS:
        if key not in cleanup:
            return False
    if not isinstance(cleanup["policy"], dict):
        return False
    if not isinstance(cleanup["pilot_block"], dict):
        return False
    if not isinstance(cleanup["slot_ref"], str) or not cleanup["slot_ref"]:
        return False
    if not isinstance(cleanup["reach_roots"], list) or not cleanup["reach_roots"]:
        return False
    if not isinstance(cleanup["run_cwd"], str) or not cleanup["run_cwd"]:
        return False
    if not isinstance(cleanup["cleanup_root"], str) or not cleanup["cleanup_root"]:
        return False
    if not isinstance(cleanup["journal_path"], str) or not cleanup["journal_path"]:
        return False
    for identity_key in (
        "observed_identity",
        "identity_provenance",
        "identity_strength",
    ):
        if not isinstance(cleanup[identity_key], str) or not cleanup[identity_key]:
            return False
    if not isinstance(cleanup["verdict"], dict):
        return False
    if not isinstance(cleanup["account"], str) or not cleanup["account"]:
        return False
    if not isinstance(cleanup["mint_envelope"], dict):
        return False
    return True


def _residual_warnings(receipt):
    warnings = []
    for entry in receipt.get("residualSentinels") or []:
        if not isinstance(entry, dict):
            continue
        namespace = entry.get("namespace")
        state = entry.get("state")
        if not isinstance(namespace, str) or not namespace:
            continue
        if not isinstance(state, str) or not state:
            continue
        warnings.append({
            "namespace": namespace[:pilot_conformance.WARNING_VALUE_MAX_LEN],
            "reason": _token_reason(state, "residual-sentinel"),
        })
    return warnings


def _warnings_when_receipt_raises(cleanup, exc):
    reason = getattr(exc, "reason", None)
    if reason != pilot_cleanup.REFUSAL_PROBE_INDETERMINATE:
        return []
    policy = cleanup["policy"]
    slot_ref = cleanup["slot_ref"]
    try:
        slot, _generation = pilot_slot.parse_slot_ref(slot_ref)
    except pilot_slot.PilotSlotError:
        return []
    foreigns = pilot_cleanup.foreign_namespaces(policy, slot)
    warnings = []
    for namespace in foreigns:
        warnings.append({
            "namespace": namespace[:pilot_conformance.WARNING_VALUE_MAX_LEN],
            "reason": "possibly-planted",
        })
    return warnings


def _effects_escape_record(pilot_block, exercised_at):
    return {
        "kind": "effects-escape",
        "declarationDigest": pilot_contract.declaration_digest(
            pilot_block["effectsEscape"]
        ),
        "exercisedAt": exercised_at,
        "receipt": {"result": "pass", "evidence": "effects do not escape"},
    }


@pilot_conformance.register("cleanup-end-to-end", surfaces=_SURFACES)
def cleanup_end_to_end_exercise(*, inputs, now):
    if not isinstance(inputs, dict):
        return _skipped_record(now)

    cleanup = inputs.get("cleanup")
    if cleanup is None:
        return _skipped_record(now)
    if not _validate_cleanup_inputs(cleanup):
        return _skipped_record(now, REASON_INPUTS_MALFORMED)

    policy = cleanup["policy"]
    pilot_block = cleanup["pilot_block"]
    slot_ref = cleanup["slot_ref"]
    run_cwd_path = cleanup["run_cwd"]
    disposable_cwd = cleanup.get("run_cwd_disposable") is True

    if not pilot_boundary.is_outside_all_reach_roots(
        run_cwd_path, cleanup["reach_roots"]
    ):
        return _fail_record(
            now,
            REASON_RUN_CWD_INSIDE_REACH,
            evidence="cleanup run_cwd must be outside all reach roots",
        )

    warnings = []
    try:
        try:
            receipt = pilot_cleanup.cleanup_effect_receipt(
                policy,
                pilot_block,
                slot_ref,
                reach_roots=cleanup["reach_roots"],
                run_cwd=run_cwd_path,
                cleanup_root=cleanup["cleanup_root"],
                journal_path=cleanup["journal_path"],
                now=now,
                observed_identity=cleanup["observed_identity"],
                identity_provenance=cleanup["identity_provenance"],
                identity_strength=cleanup["identity_strength"],
                sentinel_factory=cleanup.get("sentinel_factory"),
                timeout_seconds=cleanup.get("timeout_seconds", 20),
            )
        except pilot_cleanup.PilotCleanupError as exc:
            warnings = _warnings_when_receipt_raises(cleanup, exc)
            reason = getattr(exc, "reason", None)
            if not (
                isinstance(reason, str)
                and reason
                and not any(ch.isspace() for ch in reason)
            ):
                reason = pilot_conformance.REASON_EXERCISE_RAISED
            return _fail_record(
                now,
                reason,
                evidence="cleanup receipt construction failed",
                warnings=warnings,
            )

        warnings = _residual_warnings(receipt)

        try:
            # bite-axis: containment — a non-pass receipt must not yield a pass record.
            if receipt["result"] != pilot_cleanup.RESULT_PASS:
                return _fail_record(
                    now,
                    receipt.get("reason"),
                    evidence="cleanup receipt did not pass",
                    warnings=warnings,
                )

            registry_entry = pilot_cleanup.registry_record(receipt, pilot_block["cleanup"])
            if (
                registry_entry["kind"] != pilot_cleanup.KIND_CLEANUP_CONTAINMENT
                or registry_entry["receipt"]["result"] != pilot_cleanup.RESULT_PASS
            ):
                return _fail_record(
                    now,
                    REASON_REGISTRY_INVALID,
                    evidence="registry record invalid for passing receipt",
                    warnings=warnings,
                )

            validation = pilot_cleanup.receipt_valid_for(
                receipt,
                policy,
                pilot_block,
                slot_ref,
                cleanup_root=cleanup["cleanup_root"],
                run_cwd=run_cwd_path,
                observed_identity=cleanup["observed_identity"],
                identity_provenance=cleanup["identity_provenance"],
                identity_strength=cleanup["identity_strength"],
            )
            if not validation["ok"]:
                return _fail_record(
                    now,
                    validation.get("reason"),
                    evidence="receipt binding check failed",
                    warnings=warnings,
                    fallback=REASON_BINDING_FAILED,
                )

            containment = pilot_cleanup.resolve_containment(
                policy,
                pilot_block,
                slot_ref,
                receipt=receipt,
                cleanup_root=cleanup["cleanup_root"],
                run_cwd=run_cwd_path,
                observed_identity=cleanup["observed_identity"],
                identity_provenance=cleanup["identity_provenance"],
                identity_strength=cleanup["identity_strength"],
            )
            mode = containment.get("mode")
            if mode == pilot_cleanup.MODE_REFUSED:
                return _fail_record(
                    now,
                    containment.get("reason"),
                    evidence="containment resolution refused",
                    warnings=warnings,
                    fallback=REASON_CONTAINMENT_REFUSED,
                )
            # bite-axis: receipt-path containment — every mode other than receipt fails.
            if mode != pilot_cleanup.MODE_RECEIPT:
                return _fail_record(
                    now,
                    REASON_CONTAINMENT_NOT_RECEIPT,
                    evidence="containment did not resolve through receipt path",
                    warnings=warnings,
                )

            registry = {
                "schemaVersion": 1,
                "records": [
                    _effects_escape_record(pilot_block, now),
                    registry_entry,
                ],
            }

            plan = pilot_cleanup.resurrection_plan(
                policy,
                pilot_block,
                slot_ref,
                registry=registry,
                journal_path=cleanup["journal_path"],
                verdict=cleanup["verdict"],
                account=cleanup["account"],
                mint_envelope=cleanup["mint_envelope"],
                now=now,
                receipt=receipt,
                cleanup_root=cleanup["cleanup_root"],
                run_cwd=run_cwd_path,
                observed_identity=cleanup["observed_identity"],
                identity_provenance=cleanup["identity_provenance"],
                identity_strength=cleanup["identity_strength"],
            )

            action = plan.get("action")
            if action in (pilot_cleanup.ACTION_PARK, pilot_cleanup.ACTION_REFUSE):
                return _fail_record(
                    now,
                    plan.get("reason"),
                    evidence="resurrection plan refused or parked",
                    warnings=warnings,
                    fallback=REASON_PLAN_REFUSED,
                )
            if action != pilot_cleanup.ACTION_RESURRECT:
                return _fail_record(
                    now,
                    REASON_PLAN_NOT_RESURRECT,
                    evidence="resurrection plan action was not resurrect",
                    warnings=warnings,
                )

            return pilot_conformance.exercise_record(
                exercise=EXERCISE_NAME,
                surfaces=list(_SURFACES),
                result=pilot_conformance.RESULT_PASS,
                reason=None,
                evidence=EVIDENCE_PASS,
                exercised_at=now,
                warnings=warnings,
            )
        except Exception as exc:
            reason = getattr(exc, "reason", None)
            if not (
                isinstance(reason, str)
                and reason
                and not any(ch.isspace() for ch in reason)
            ):
                reason = pilot_conformance.REASON_EXERCISE_RAISED
            return _fail_record(
                now,
                reason,
                evidence="post-plant failure: %s" % type(exc).__name__,
                warnings=warnings,
            )
    finally:
        if disposable_cwd and os.path.isdir(run_cwd_path):
            shutil.rmtree(run_cwd_path, ignore_errors=True)
