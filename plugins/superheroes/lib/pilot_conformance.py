"""Headless conformance-run contract for pilot framework surface exercise (C10).

Grades exercise records against a closed required-surface inventory so a conformance
report that skips a surface must never read as covered.

Sibling modules own registered exercise functions; this module owns the record
contract, report aggregation, run harness, default exercise assembly, input resolution,
and CLI entry point.
"""
import argparse
import datetime
import json
import os
import re
import sys
from datetime import timezone

import store

SCHEMA = 1

RESULT_PASS = "pass"
RESULT_FAIL = "fail"
RESULT_SKIPPED = "skipped"
RESULT_REFUSED = "refused"
EXERCISE_RESULTS = frozenset({RESULT_PASS, RESULT_FAIL, RESULT_SKIPPED, RESULT_REFUSED})

REQUIRED_SURFACES = (
    "pilot_appctl.assert_unique_endpoints",
    "pilot_appctl.resolve_invocation",
    "pilot_artifacts.retain",
    "pilot_artifacts.sweep",
    "pilot_cleanup.cleanup_effect_receipt",
    "pilot_cleanup.receipt_valid_for",
    "pilot_cleanup.registry_record",
    "pilot_cleanup.resolve_containment",
    "pilot_cleanup.resurrection_plan",
    "pilot_mint.gate_off_receipt",
    "pilot_mint.run_gate_off_test",
    "pilot_reclaim.sweep",
    "pilot_wave.admit_work",
    "pilot_wave.assert_destructive_allowed",
    "pilot_wave.validate_step_result",
    "pilot_wave.wave_anchor",
    "pilot_wave.wave_phase",
)

REASON_RECORD_INVALID = "conformance-record-invalid"
REASON_RECORD_UNREGISTERED = "conformance-record-unregistered"
REASON_RESULT_INVALID = "conformance-result-invalid"
REASON_EXERCISE_NAME_INVALID = "conformance-exercise-name-invalid"
REASON_EXERCISE_NAME_DUPLICATE = "conformance-exercise-name-duplicate"
REASON_SURFACES_EMPTY = "conformance-surfaces-empty"
REASON_SURFACE_UNKNOWN = "conformance-surface-unknown"
REASON_SURFACE_DUPLICATE = "conformance-surface-duplicate"
REASON_REASON_INVALID = "conformance-reason-invalid"
REASON_EVIDENCE_INVALID = "conformance-evidence-invalid"
REASON_EXERCISED_AT_INVALID = "conformance-exercised-at-invalid"
REASON_REQUIRED_SURFACES_INVALID = "conformance-required-surfaces-invalid"
REASON_WARNING_INVALID = "conformance-warning-invalid"
REASON_EXERCISE_FN_INVALID = "conformance-exercise-fn-invalid"
REASON_EXERCISE_RAISED = "conformance-exercise-raised"

REASON_INPUT_NO_CALIBRATION = "conformance-input-no-calibration"
REASON_INPUT_NO_PILOT_BLOCK = "conformance-input-no-pilot-block"
REASON_INPUT_PILOT_BLOCK_INVALID = "conformance-input-pilot-block-invalid"
REASON_INPUT_NO_POLICY_ROOT = "conformance-input-no-policy-root"
REASON_INPUT_NO_SLOTS_DIR = "conformance-input-no-slots-dir"
REASON_INPUT_NO_SLOT_REF = "conformance-input-no-slot-ref"
REASON_INPUT_NO_SLOT = "conformance-input-no-slot"
REASON_INPUT_BRANCH_UNRESOLVED = "conformance-input-branch-unresolved"
REASON_INPUT_NO_MATERIAL = "conformance-input-no-material"
REASON_INPUT_NO_ARTIFACTS_DIR = "conformance-input-no-artifacts-dir"
REASON_INPUT_POLICY_UNRESOLVED = "conformance-input-policy-unresolved"
REASON_INPUT_NO_MINT = "conformance-input-no-mint"
REASON_INPUT_CLEANUP_INCOMPLETE = "conformance-input-cleanup-incomplete"

REASON_CLI_CWD_INVALID = "conformance-cli-cwd-invalid"
REASON_CLI_NOW_INVALID = "conformance-cli-now-invalid"

_EXERCISE_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}\Z")
EVIDENCE_MAX_LEN = 500
WARNING_VALUE_MAX_LEN = 200
REASON_TOKEN_MAX_LEN = 64

_REQUIRED_RECORD_KEYS = frozenset({
    "schemaVersion",
    "exercise",
    "surfaces",
    "result",
    "reason",
    "evidence",
    "exercisedAt",
    "warnings",
})


class PilotConformanceError(Exception):
    """Conformance-contract refusal."""

    def __init__(self, reason, detail=None):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


def _has_control_char(value):
    return any(ord(ch) < 32 for ch in value)


def _validate_exercise_name(exercise):
    if not isinstance(exercise, str) or not _EXERCISE_NAME_RE.match(exercise):
        raise PilotConformanceError(REASON_EXERCISE_NAME_INVALID)


def _validate_surfaces(surfaces):
    if not isinstance(surfaces, list) or not surfaces:
        raise PilotConformanceError(REASON_SURFACES_EMPTY)
    seen = set()
    for surface in surfaces:
        # bite-axis: closed surface inventory — only REQUIRED_SURFACES members accepted.
        if not isinstance(surface, str) or surface not in REQUIRED_SURFACES:
            raise PilotConformanceError(REASON_SURFACE_UNKNOWN)
        if surface in seen:
            raise PilotConformanceError(REASON_SURFACE_DUPLICATE)
        seen.add(surface)


def _validate_result(result):
    # bite-axis: result membership — only string tokens in EXERCISE_RESULTS; truthy non-strings refuse.
    if not isinstance(result, str) or result not in EXERCISE_RESULTS:
        raise PilotConformanceError(REASON_RESULT_INVALID)


def _validate_reason(result, reason):
    if result == RESULT_PASS:
        if reason is not None:
            raise PilotConformanceError(REASON_REASON_INVALID)
        return
    if (
        not isinstance(reason, str)
        or not reason
        or reason.isspace()
        or any(ch.isspace() for ch in reason)
        or len(reason) > REASON_TOKEN_MAX_LEN
    ):
        raise PilotConformanceError(REASON_REASON_INVALID)


def _validate_evidence(evidence):
    if (
        not isinstance(evidence, str)
        or not evidence
        or len(evidence) > EVIDENCE_MAX_LEN
        or _has_control_char(evidence)
    ):
        raise PilotConformanceError(REASON_EVIDENCE_INVALID)


def _validate_exercised_at(exercised_at):
    if not isinstance(exercised_at, str):
        raise PilotConformanceError(REASON_EXERCISED_AT_INVALID)
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ"):
        try:
            datetime.datetime.strptime(exercised_at, fmt)
            return
        except ValueError:
            continue
    raise PilotConformanceError(REASON_EXERCISED_AT_INVALID)


def _validate_warnings(warnings):
    if warnings is None:
        return []
    if not isinstance(warnings, list):
        raise PilotConformanceError(REASON_WARNING_INVALID)
    normalized = []
    for warning in warnings:
        if not isinstance(warning, dict):
            raise PilotConformanceError(REASON_WARNING_INVALID)
        if "exercise" in warning:
            raise PilotConformanceError(REASON_WARNING_INVALID)
        copy = {}
        for key, value in warning.items():
            if (
                not isinstance(key, str)
                or not key
                or len(key) > WARNING_VALUE_MAX_LEN
                or _has_control_char(key)
                or not isinstance(value, str)
                or not value
                or len(value) > WARNING_VALUE_MAX_LEN
                or _has_control_char(value)
            ):
                raise PilotConformanceError(REASON_WARNING_INVALID)
            copy[key] = value
        normalized.append(copy)
    return normalized


def exercise_record(*, exercise, surfaces, result, reason, evidence, exercised_at, warnings=None):
    """Build and validate a canonical conformance exercise record."""
    _validate_exercise_name(exercise)
    _validate_surfaces(surfaces)
    _validate_result(result)
    _validate_reason(result, reason)
    _validate_evidence(evidence)
    _validate_exercised_at(exercised_at)
    warnings_normalized = _validate_warnings(warnings)
    return {
        "schemaVersion": SCHEMA,
        "exercise": exercise,
        "surfaces": sorted(surfaces),
        "result": result,
        "reason": reason,
        "evidence": evidence,
        "exercisedAt": exercised_at,
        "warnings": warnings_normalized,
    }


def validate_record(record):
    """Re-validate a record dict built elsewhere."""
    if not isinstance(record, dict):
        raise PilotConformanceError(REASON_RECORD_INVALID)
    keys = set(record.keys())
    if keys != _REQUIRED_RECORD_KEYS:
        raise PilotConformanceError(REASON_RECORD_INVALID)
    if record.get("schemaVersion") != SCHEMA:
        raise PilotConformanceError(REASON_RECORD_INVALID)
    exercise_record(
        exercise=record["exercise"],
        surfaces=record["surfaces"],
        result=record["result"],
        reason=record["reason"],
        evidence=record["evidence"],
        exercised_at=record["exercisedAt"],
        warnings=record["warnings"],
    )
    return record


def _validate_required_surfaces(required_surfaces):
    if not isinstance(required_surfaces, (tuple, list)) or not required_surfaces:
        raise PilotConformanceError(REASON_REQUIRED_SURFACES_INVALID)
    seen = set()
    for surface in required_surfaces:
        if not isinstance(surface, str) or not surface:
            raise PilotConformanceError(REASON_REQUIRED_SURFACES_INVALID)
        if surface in seen:
            raise PilotConformanceError(REASON_REQUIRED_SURFACES_INVALID)
        seen.add(surface)


def report(records, *, required_surfaces=REQUIRED_SURFACES):
    """Aggregate validated exercise records into a conformance report."""
    _validate_required_surfaces(required_surfaces)
    if not isinstance(records, list):
        raise PilotConformanceError(REASON_RECORD_INVALID)

    validated = []
    seen_exercises = set()
    for record in records:
        validated_record = validate_record(record)
        exercise_name = validated_record["exercise"]
        # bite-axis: exercise-name uniqueness — duplicate exercise names refuse at report time.
        if exercise_name in seen_exercises:
            raise PilotConformanceError(REASON_EXERCISE_NAME_DUPLICATE)
        seen_exercises.add(exercise_name)
        validated.append(validated_record)

    # bite-axis: coverage honesty — only pass records contribute to covered; unexercised is set difference.
    covered = set()
    for record in validated:
        if record["result"] == RESULT_PASS:
            covered.update(record["surfaces"])

    unexercised = sorted(set(required_surfaces) - covered)

    warnings = []
    for record in validated:
        for warning in record["warnings"]:
            warning_copy = dict(warning)
            warning_copy["exercise"] = record["exercise"]
            warnings.append(warning_copy)

    ok = (
        bool(validated)
        and not unexercised
        and all(record["result"] == RESULT_PASS for record in validated)
    )

    return {
        "schemaVersion": SCHEMA,
        "ok": ok,
        "exercises": validated,
        "surfaces": sorted(covered),
        "unexercised": unexercised,
        "warnings": warnings,
    }


def register(name, *, surfaces):
    """Decorator marking a callable as a conformance exercise function."""
    _validate_exercise_name(name)
    if not isinstance(surfaces, (list, tuple)):
        raise PilotConformanceError(REASON_SURFACES_EMPTY)
    _validate_surfaces(list(surfaces))

    def decorator(fn):
        fn.conformance_exercise = name
        fn.conformance_surfaces = tuple(sorted(surfaces))
        return fn

    return decorator


def _validate_exercise_fn(fn):
    if not callable(fn):
        raise PilotConformanceError(REASON_EXERCISE_FN_INVALID)
    exercise_name = getattr(fn, "conformance_exercise", None)
    exercise_surfaces = getattr(fn, "conformance_surfaces", None)
    if not isinstance(exercise_name, str) or not _EXERCISE_NAME_RE.match(exercise_name):
        raise PilotConformanceError(REASON_EXERCISE_FN_INVALID)
    if not isinstance(exercise_surfaces, tuple):
        raise PilotConformanceError(REASON_EXERCISE_FN_INVALID)
    try:
        _validate_surfaces(list(exercise_surfaces))
    except PilotConformanceError:
        raise PilotConformanceError(REASON_EXERCISE_FN_INVALID)


def _normalize_exception_reason(exc):
    reason = getattr(exc, "reason", None)
    if (
        isinstance(reason, str)
        and reason
        and not any(ch.isspace() for ch in reason)
        and len(reason) <= REASON_TOKEN_MAX_LEN
    ):
        return reason
    return REASON_EXERCISE_RAISED


def run(exercise_fns, *, inputs, now):
    """Run registered exercise functions and return an aggregated conformance report."""
    if not isinstance(exercise_fns, list):
        raise PilotConformanceError(REASON_EXERCISE_FN_INVALID)
    for fn in exercise_fns:
        _validate_exercise_fn(fn)

    records = []
    for fn in exercise_fns:
        exercise_name = fn.conformance_exercise
        exercise_surfaces = list(fn.conformance_surfaces)
        try:
            returned = fn(inputs=inputs, now=now)
            try:
                record = validate_record(returned)
                # bite-axis: registration honesty — record must not claim unregistered coverage.
                if (
                    record["exercise"] != exercise_name
                    or not set(record["surfaces"]).issubset(set(exercise_surfaces))
                ):
                    records.append(exercise_record(
                        exercise=exercise_name,
                        surfaces=exercise_surfaces,
                        result=RESULT_FAIL,
                        reason=REASON_RECORD_UNREGISTERED,
                        evidence="exercise record claims unregistered coverage",
                        exercised_at=now,
                    ))
                else:
                    records.append(record)
            except PilotConformanceError:
                records.append(exercise_record(
                    exercise=exercise_name,
                    surfaces=exercise_surfaces,
                    result=RESULT_FAIL,
                    reason=REASON_RECORD_INVALID,
                    evidence="exercise returned an invalid record",
                    exercised_at=now,
                ))
        except Exception as exc:
            # bite-axis: exercise exception normalization — never propagate; evidence is class name only.
            records.append(exercise_record(
                exercise=exercise_name,
                surfaces=exercise_surfaces,
                result=RESULT_FAIL,
                reason=_normalize_exception_reason(exc),
                evidence="exercise raised %s" % type(exc).__name__,
                exercised_at=now,
            ))

    return report(records)


def default_exercises():
    """Return registered exercise callables in stable declared order."""
    import pilot_conformance_cleanup
    import pilot_conformance_runtime as runtime

    return [
        runtime.artifact_store_exercise,
        pilot_conformance_cleanup.cleanup_end_to_end_exercise,
        runtime.mint_gate_off_exercise,
        runtime.reclaim_sweep_exercise,
        runtime.wave_headless_exercise,
    ]


def _resolution_entry(resolution, input_key, *, resolved, reason=None):
    resolution.append({
        "input": input_key,
        "state": "resolved" if resolved else "absent",
        "reason": reason,
    })


def _flatten_policy_material(material):
    if not isinstance(material, dict):
        return []
    items = []
    for values in material.values():
        if not isinstance(values, list):
            continue
        for value in values:
            if isinstance(value, str) and value:
                items.append(value)
    return sorted(set(items))


def _load_calibration_config(cwd, store_root):
    """Follow pilot_calibration's resolution path; return (config, profile_path)."""
    import pilot_calibration

    # pilot_calibration's public API (declares_slots) does not expose config extraction;
    # _read_calibration_text is required to load the pilot block for resolve_inputs.
    try:
        info = store.resolve(cwd, store_root)
        path = info.get("profile") if info.get("exists") else None
    except Exception:
        return None, None
    if path is None:
        try:
            candidates = store.candidate_profile_paths(cwd, store_root)
        except Exception:
            return None, None
        for candidate in candidates:
            text, read_cause = pilot_calibration._read_calibration_text(candidate)
            if read_cause == "not-found":
                continue
            if read_cause is not None:
                return None, candidate
            match = store.CONFIG_BLOCK_RE.search(text)
            if match is None:
                return None, candidate
            try:
                cfg = json.loads(match.group(1))
            except (json.JSONDecodeError, TypeError, ValueError):
                return None, candidate
            if isinstance(cfg, dict):
                return cfg, candidate
            return None, candidate
        return None, None
    text, read_cause = pilot_calibration._read_calibration_text(path)
    if read_cause is not None:
        return None, path
    match = store.CONFIG_BLOCK_RE.search(text)
    if not match:
        return None, path
    try:
        cfg = json.loads(match.group(1))
    except (json.JSONDecodeError, TypeError, ValueError):
        return None, path
    if not isinstance(cfg, dict):
        return None, path
    return cfg, path


def _resolve_branch(cwd, branch):
    # bite-axis: honest absence — git-unavailable branch stays absent; never synthesize "main".
    if isinstance(branch, str) and branch:
        return branch
    import store_core

    resolved = store_core.run_git(cwd, "rev-parse", "--abbrev-ref", "HEAD")
    if isinstance(resolved, str) and resolved:
        return resolved
    return None


def _resolve_slot_name(slot, slot_ref):
    if isinstance(slot, str) and slot:
        return slot
    if not isinstance(slot_ref, str) or not slot_ref:
        return None
    import pilot_slot

    try:
        parsed_slot, _generation = pilot_slot.parse_slot_ref(slot_ref)
    except pilot_slot.PilotSlotError:
        return None
    return parsed_slot


def _build_cleanup_verdict(policy, slot_ref, now):
    import pilot_boundary
    import pilot_contract

    policy_digest = pilot_contract.declaration_digest(policy)
    return pilot_boundary.boundary_verdict(
        {"slotRef": slot_ref},
        checks=[
            ("target-binding", {"ok": True, "reason": None}),
            ("datastore-identity", {"ok": True, "reason": None}),
        ],
        policy_digest=policy_digest,
        verified_at=now,
    )


def resolve_inputs(cwd, *, policy_root=None, reach_roots=None, slots_dir=None,
                   slot_ref=None, branch=None, slot=None, artifacts_dir=None,
                   store_root=None, now=None):
    """Assemble exercise inputs and a per-key resolution audit trail."""
    import pilot_contract
    import pilot_policy

    if now is None:
        now = datetime.datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    resolution = []
    inputs = {}
    root = store_root if store_root is not None else store.store_root()

    cfg, _profile_path = _load_calibration_config(cwd, root)
    pilot_block = None
    pilot_reason = REASON_INPUT_NO_CALIBRATION
    if cfg is None:
        pilot_reason = REASON_INPUT_NO_CALIBRATION
    elif pilot_contract.PILOT_BLOCK_KEY not in cfg:
        pilot_reason = REASON_INPUT_NO_PILOT_BLOCK
    else:
        candidate = cfg[pilot_contract.PILOT_BLOCK_KEY]
        if not isinstance(candidate, dict):
            pilot_reason = REASON_INPUT_PILOT_BLOCK_INVALID
        else:
            try:
                pilot_contract.validate_pilot_block(candidate)
            except pilot_contract.PilotContractError:
                pilot_reason = REASON_INPUT_PILOT_BLOCK_INVALID
            else:
                pilot_block = candidate

    resolved_branch = _resolve_branch(cwd, branch)
    resolved_artifacts_dir = artifacts_dir
    if resolved_artifacts_dir is None:
        try:
            resolved_artifacts_dir = store.resolve(cwd, root)["artifacts_dir"]
        except Exception:
            resolved_artifacts_dir = None

    resolved_slot = _resolve_slot_name(slot, slot_ref)
    policy = None
    material = []
    policy_reason = None
    if pilot_block is not None:
        if policy_root is None:
            policy_reason = REASON_INPUT_NO_POLICY_ROOT
        else:
            reach = list(reach_roots) if reach_roots is not None else [os.path.realpath(cwd)]
            declaration = pilot_block.get("policyRef", {}).get("declaration")
            if not isinstance(declaration, str) or not declaration:
                policy_reason = REASON_INPUT_POLICY_UNRESOLVED
            else:
                try:
                    policy = pilot_policy.resolve_policy_document(
                        policy_root,
                        declaration,
                        reach_roots=reach,
                    )
                    material = _flatten_policy_material(
                        pilot_policy.policy_material(policy)
                    )
                except pilot_policy.PilotPolicyError as exc:
                    reason = getattr(exc, "reason", None)
                    if (
                        isinstance(reason, str)
                        and reason
                        and not any(ch.isspace() for ch in reason)
                    ):
                        policy_reason = reason
                    else:
                        policy_reason = REASON_INPUT_POLICY_UNRESOLVED

    if (
        resolved_artifacts_dir
        and resolved_branch
        and resolved_slot
        and material
    ):
        inputs["artifacts"] = {
            "artifacts_dir": resolved_artifacts_dir,
            "branch": resolved_branch,
            "slot": resolved_slot,
            "material": material,
        }
        _resolution_entry(resolution, "artifacts", resolved=True)
    else:
        if pilot_block is None:
            artifacts_reason = pilot_reason
        elif resolved_artifacts_dir is None:
            artifacts_reason = REASON_INPUT_NO_ARTIFACTS_DIR
        elif resolved_branch is None:
            artifacts_reason = REASON_INPUT_BRANCH_UNRESOLVED
        elif not material:
            artifacts_reason = REASON_INPUT_NO_MATERIAL
        elif resolved_slot is None:
            artifacts_reason = REASON_INPUT_NO_SLOT
        else:
            artifacts_reason = REASON_INPUT_NO_MATERIAL
        _resolution_entry(resolution, "artifacts", resolved=False, reason=artifacts_reason)

    cleanup = None
    cleanup_reason = pilot_reason if pilot_block is None else None
    if pilot_block is not None and cleanup_reason is None:
        if policy_root is None:
            cleanup_reason = REASON_INPUT_NO_POLICY_ROOT
        elif policy is None:
            cleanup_reason = policy_reason or REASON_INPUT_POLICY_UNRESOLVED
        elif slots_dir is None or not os.path.isdir(slots_dir):
            cleanup_reason = REASON_INPUT_NO_SLOTS_DIR
        elif not isinstance(slot_ref, str) or not slot_ref:
            cleanup_reason = REASON_INPUT_NO_SLOT_REF
        else:
            reach = list(reach_roots) if reach_roots is not None else [os.path.realpath(cwd)]
            if not reach:
                cleanup_reason = REASON_INPUT_CLEANUP_INCOMPLETE
            else:
                try:
                    cleanup_root = store.get_repo_root(cwd)
                except Exception:
                    cleanup_root = os.path.realpath(cwd)
                slot_name = _resolve_slot_name(slot, slot_ref)
                if slot_name is None:
                    cleanup_reason = REASON_INPUT_NO_SLOT
                else:
                    journal_path = os.path.join(slots_dir, slot_name, "journal.ndjson")
                    credential_set = pilot_block.get("credentialSet") or []
                    account = None
                    if credential_set and isinstance(credential_set[0], dict):
                        account = credential_set[0].get("account")
                    mint_block = pilot_block.get("mint")
                    mint_envelope = (
                        mint_block.get("envelope")
                        if isinstance(mint_block, dict)
                        else None
                    )
                    observed_identity = policy.get("datastore", {}).get("expectedIdentity")
                    if (
                        isinstance(account, str)
                        and account
                        and isinstance(mint_envelope, dict)
                        and isinstance(observed_identity, str)
                        and observed_identity
                    ):
                        cleanup = {
                            "policy": policy,
                            "pilot_block": pilot_block,
                            "slot_ref": slot_ref,
                            "reach_roots": reach,
                            "run_cwd": cwd,
                            "cleanup_root": cleanup_root,
                            "journal_path": journal_path,
                            "observed_identity": observed_identity,
                            "identity_provenance": "observed",
                            "identity_strength": "strong",
                            "verdict": _build_cleanup_verdict(policy, slot_ref, now),
                            "account": account,
                            "mint_envelope": mint_envelope,
                        }
                    else:
                        cleanup_reason = REASON_INPUT_CLEANUP_INCOMPLETE

    if cleanup is not None:
        inputs["cleanup"] = cleanup
        _resolution_entry(resolution, "cleanup", resolved=True)
    else:
        _resolution_entry(
            resolution,
            "cleanup",
            resolved=False,
            reason=cleanup_reason or REASON_INPUT_CLEANUP_INCOMPLETE,
        )

    mint = None
    mint_reason = pilot_reason if pilot_block is None else None
    if pilot_block is not None and mint_reason is None:
        mint_block = pilot_block.get("mint")
        envelope = mint_block.get("envelope") if isinstance(mint_block, dict) else None
        env_var = envelope.get("enablingFlagEnvVar") if isinstance(envelope, dict) else None
        if not isinstance(envelope, dict) or not isinstance(env_var, str) or not env_var:
            mint_reason = REASON_INPUT_NO_MINT
        elif not os.path.isdir(cwd):
            mint_reason = REASON_INPUT_CLEANUP_INCOMPLETE
        else:
            path_value = os.environ.get("PATH", os.defpath)
            mint = {
                "envelope": envelope,
                "run_cwd": cwd,
                "environment": {env_var: "1", "PATH": path_value},
            }

    if mint is not None:
        inputs["mint"] = mint
        _resolution_entry(resolution, "mint", resolved=True)
    else:
        _resolution_entry(
            resolution,
            "mint",
            resolved=False,
            reason=mint_reason or REASON_INPUT_NO_MINT,
        )

    if slots_dir is not None and os.path.isdir(slots_dir):
        wave = {"slots_dir": slots_dir}
        if isinstance(slot_ref, str) and slot_ref:
            wave["slot_ref"] = slot_ref
            inputs["wave"] = wave
            _resolution_entry(resolution, "wave", resolved=True)
        else:
            _resolution_entry(resolution, "wave", resolved=False, reason=REASON_INPUT_NO_SLOT_REF)
        inputs["reclaim"] = {"slots_dir": slots_dir}
        _resolution_entry(resolution, "reclaim", resolved=True)
    else:
        _resolution_entry(resolution, "wave", resolved=False, reason=REASON_INPUT_NO_SLOTS_DIR)
        _resolution_entry(resolution, "reclaim", resolved=False, reason=REASON_INPUT_NO_SLOTS_DIR)

    return inputs, resolution


def _validate_cli_now(now):
    if not isinstance(now, str):
        raise PilotConformanceError(REASON_CLI_NOW_INVALID)
    try:
        _validate_exercised_at(now)
    except PilotConformanceError:
        raise PilotConformanceError(REASON_CLI_NOW_INVALID)
    return now


def _parse_run_args(args):
    parser = argparse.ArgumentParser(prog="pilot_conformance.py")
    subparsers = parser.add_subparsers(dest="command")
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--cwd", required=True)
    run_parser.add_argument("--policy-root")
    run_parser.add_argument("--reach-root", action="append", dest="reach_roots", default=[])
    run_parser.add_argument("--slots-dir")
    run_parser.add_argument("--slot-ref")
    run_parser.add_argument("--branch")
    run_parser.add_argument("--slot")
    run_parser.add_argument("--artifacts-dir")
    run_parser.add_argument("--now")
    parsed = parser.parse_args(args)
    if parsed.command != "run":
        parser.print_usage(sys.stderr)
        return None
    return parsed


def main(argv):
    """CLI entry point for the conformance run."""
    args = argv[1:]
    if not args:
        sys.stderr.write("Usage: pilot_conformance.py run --cwd <path> [options]\n")
        return 2

    parsed = _parse_run_args(args)
    if parsed is None:
        return 2

    cwd = os.path.realpath(parsed.cwd)
    if not os.path.isdir(cwd):
        sys.stderr.write("%s\n" % REASON_CLI_CWD_INVALID)
        return 2

    if parsed.now is None:
        now = datetime.datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        try:
            now = _validate_cli_now(parsed.now)
        except PilotConformanceError as exc:
            sys.stderr.write("%s\n" % exc.reason)
            return 2

    reach_roots = parsed.reach_roots or None
    try:
        inputs, resolution = resolve_inputs(
            cwd,
            policy_root=parsed.policy_root,
            reach_roots=reach_roots,
            slots_dir=parsed.slots_dir,
            slot_ref=parsed.slot_ref,
            branch=parsed.branch,
            slot=parsed.slot,
            artifacts_dir=parsed.artifacts_dir,
            now=now,
        )
        report_data = run(default_exercises(), inputs=inputs, now=now)
    except PilotConformanceError as exc:
        sys.stderr.write("%s\n" % exc.reason)
        return 2

    output = dict(report_data)
    output["resolution"] = resolution
    # bite-axis: stdout/stderr split — report JSON only on stdout; diagnostics belong on stderr.
    sys.stdout.write(json.dumps(output, indent=2) + "\n")
    # bite-axis: all-skipped honesty — ok false must exit 1, never 0.
    return 0 if report_data["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
