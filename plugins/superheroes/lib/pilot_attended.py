"""Attended seeding plans and verify-at-seed verdicts for the pilot wave runtime (B4).

Pure, side-effect-free: produces plans and verdicts for a headed owner sign-in flow.
No browser driving, no I/O, no credential capture or storage.

Non-goals: no browser launch, no network I/O, no credential capture, reduction, storage,
or transfer — the wave runtime executes these plans.
"""
import hmac

import pilot_contract
import pilot_identity
import pilot_probe
import pilot_seed
import pilot_slot

REFUSAL_SIGN_IN_PATH_NOT_ATTENDED = "attended-sign-in-path-not-attended"
REFUSAL_VEHICLE_INVALID = "attended-vehicle-invalid"
REFUSAL_VEHICLE_UNSUPPORTED_MECHANISM = "attended-vehicle-unsupported-mechanism"
REFUSAL_ACCOUNT_SET_EMPTY = "attended-account-set-empty"
REFUSAL_ACCOUNT_SET_MISMATCH = "attended-account-set-mismatch"
REFUSAL_EXPECTED_IDENTITY_MISSING = "attended-expected-identity-missing"
REFUSAL_EXPECTED_IDENTITY_INVALID = "attended-expected-identity-invalid"
REFUSAL_IDENTITY_MISMATCH = "attended-identity-mismatch"
REFUSAL_IDENTITY_ABSENT = "attended-identity-absent"
REFUSAL_ANSWER_INVALID = "attended-answer-invalid"
REFUSAL_SLOT_REF_INVALID = "attended-slot-ref-invalid"
REFUSAL_ACCOUNT_INVALID = "attended-account-invalid"
REFUSAL_CONTEXT_REUSED = "attended-context-reused"
REFUSAL_SEED_INCOMPLETE = "attended-seed-incomplete"

OUTCOME_VERIFIED = "verified"
OUTCOME_REFUSED = "refused"
OUTCOME_PARKED = "parked"

_SLOT_REFUSALS = frozenset({
    pilot_slot.REFUSAL_SLOT_ID_INVALID,
    pilot_slot.REFUSAL_GENERATION_INVALID,
    pilot_slot.REFUSAL_SLOT_REF_MALFORMED,
})

_ACCOUNT_REFUSALS = frozenset({
    pilot_slot.REFUSAL_ACCOUNT_ENTRY_INVALID,
    pilot_slot.REFUSAL_ACCOUNT_ROLE_MISSING,
})


class PilotAttendedError(Exception):
    """Attended-seeding refusal."""

    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def _refusal(reason):
    return {"ok": False, "reason": reason}


def _validate_expected_identity(expected_identity):
    if not isinstance(expected_identity, str) or not expected_identity:
        raise PilotAttendedError(REFUSAL_EXPECTED_IDENTITY_INVALID)


def _normalize_answer(answer):
    if not isinstance(answer, dict):
        return None, REFUSAL_ANSWER_INVALID
    identity = answer.get("identity")
    reason = answer.get("reason")
    has_identity = identity is not None
    has_reason = reason is not None
    if has_identity and has_reason or not has_identity and not has_reason:
        return None, REFUSAL_ANSWER_INVALID
    try:
        return pilot_identity.probe_answer(identity=identity, reason=reason), None
    except pilot_identity.PilotIdentityError:
        return None, REFUSAL_ANSWER_INVALID


def _map_slot_error(exc):
    reason = exc.reason
    if reason == pilot_slot.REFUSAL_ACCOUNT_SET_EMPTY:
        return REFUSAL_ACCOUNT_SET_EMPTY
    if reason == pilot_slot.REFUSAL_ACCOUNT_DUPLICATE:
        return REFUSAL_CONTEXT_REUSED
    if reason in _SLOT_REFUSALS:
        return REFUSAL_SLOT_REF_INVALID
    if reason in _ACCOUNT_REFUSALS:
        return REFUSAL_ACCOUNT_INVALID
    return REFUSAL_SLOT_REF_INVALID


def _lapse_outcome(action):
    if action == pilot_identity.ACTION_PARK:
        return OUTCOME_PARKED
    if action == pilot_identity.ACTION_CONTINUE:
        return OUTCOME_VERIFIED
    return OUTCOME_REFUSED


def seeding_vehicle(
    attended_declaration,
    *,
    idp_rejects_automation,
    human_driven_rejected=False,
):
    """Return the browser vehicle string for attended seeding."""
    # bite-axis: vehicle escalation — real-chrome when declared or when IdP rejects automation.
    if type(human_driven_rejected) is not bool:
        return _refusal(REFUSAL_VEHICLE_INVALID)
    if human_driven_rejected:
        return _refusal(REFUSAL_VEHICLE_UNSUPPORTED_MECHANISM)
    if type(idp_rejects_automation) is not bool:
        return _refusal(REFUSAL_VEHICLE_INVALID)
    if not isinstance(attended_declaration, dict):
        return _refusal(REFUSAL_VEHICLE_INVALID)
    vehicle = attended_declaration.get("vehicle")
    if not isinstance(vehicle, str) or vehicle not in pilot_contract.ATTENDED_VEHICLES:
        return _refusal(REFUSAL_VEHICLE_INVALID)
    if vehicle == "real-chrome":
        return "real-chrome"
    if idp_rejects_automation:
        return "real-chrome"
    return "automation"


def prompt_copy(slot_ref, account, expected_identity, vehicle):
    """Plain-language owner prompt for one attended sign-in step."""
    lines = [
        "Sign in to pilot slot %s as account %s." % (slot_ref, account),
        "The signed-in identity must be exactly %s." % expected_identity,
        "Use the dedicated pilot account for this slot, not your personal account.",
        "Nothing from this sign-in is recorded or saved.",
    ]
    if vehicle == "real-chrome":
        lines.append(
            "A real Chrome window with a fresh profile is opening because the "
            "identity provider refuses automated browsers."
        )
    return " ".join(lines)


def verify_at_seed(answer, *, expected_identity):
    """Identity half of verify-at-seed for the attended path (no artifact)."""
    # bite-axis: identity comparison — hmac.compare_digest on UTF-8; wrong identity refuses.
    _validate_expected_identity(expected_identity)

    normalized, refusal = _normalize_answer(answer)
    if refusal is not None:
        return {
            "ok": False,
            "outcome": OUTCOME_REFUSED,
            "reason": refusal,
            "identity": None,
        }

    if normalized["identity"] is not None:
        if hmac.compare_digest(
            normalized["identity"].encode("utf-8"),
            expected_identity.encode("utf-8"),
        ):
            return {
                "ok": True,
                "outcome": OUTCOME_VERIFIED,
                "reason": None,
                "identity": normalized["identity"],
            }
        return {
            "ok": False,
            "outcome": OUTCOME_REFUSED,
            "reason": REFUSAL_IDENTITY_MISMATCH,
            "identity": normalized["identity"],
        }

    return {
        "ok": False,
        "outcome": OUTCOME_REFUSED,
        "reason": REFUSAL_IDENTITY_ABSENT,
        "identity": None,
    }


def attended_seeding_plan(
    slot,
    generation,
    accounts,
    *,
    sign_in_path,
    attended_declaration,
    capture_surfaces,
    expected_identities,
    idp_rejects_automation=False,
    human_driven_rejected=False,
):
    """Build the per-account attended sign-in plan for one slot."""
    if not isinstance(sign_in_path, str) or sign_in_path not in pilot_contract.SIGN_IN_PATHS:
        return _refusal(REFUSAL_SIGN_IN_PATH_NOT_ATTENDED)
    if sign_in_path != "attended":
        return _refusal(REFUSAL_SIGN_IN_PATH_NOT_ATTENDED)

    # bite-axis: account-set alignment — expected_identities keys must match slot accounts exactly.
    try:
        account_set = pilot_slot.slot_account_set(slot, generation, accounts)
    except pilot_slot.PilotSlotError as exc:
        return _refusal(_map_slot_error(exc))

    vehicle_result = seeding_vehicle(
        attended_declaration,
        idp_rejects_automation=idp_rejects_automation,
        human_driven_rejected=human_driven_rejected,
    )
    if isinstance(vehicle_result, dict):
        return vehicle_result

    vehicle = vehicle_result
    slot_ref = account_set["ref"]
    account_list = pilot_slot.account_keys(account_set)

    if not isinstance(expected_identities, dict):
        return _refusal(REFUSAL_ACCOUNT_SET_MISMATCH)

    expected_keys = set(expected_identities.keys())
    account_keys_set = set(account_list)
    if expected_keys != account_keys_set:
        return _refusal(REFUSAL_ACCOUNT_SET_MISMATCH)

    try:
        context_options = pilot_seed.required_context_options(capture_surfaces)
    except pilot_seed.PilotSeedError as exc:
        return _refusal(exc.reason)

    steps = []
    seen_pairs = set()
    for account in account_list:
        pair = (slot_ref, account)
        if pair in seen_pairs:
            return _refusal(REFUSAL_CONTEXT_REUSED)
        seen_pairs.add(pair)

        expected_identity = expected_identities[account]
        if expected_identity is None:
            return _refusal(REFUSAL_EXPECTED_IDENTITY_MISSING)
        if not isinstance(expected_identity, str) or not expected_identity:
            return _refusal(REFUSAL_EXPECTED_IDENTITY_INVALID)

        steps.append({
            "slotRef": slot_ref,
            "account": account,
            "vehicle": vehicle,
            "contextOptions": {
                "indexedDB": context_options["indexedDB"],
                "credentials": context_options["credentials"],
            },
            "expectedIdentity": expected_identity,
            "prompt": prompt_copy(slot_ref, account, expected_identity, vehicle),
        })

    return {
        "ok": True,
        "reason": None,
        "slotRef": slot_ref,
        "vehicle": vehicle,
        "steps": steps,
    }


def seed_outcome(steps, results):
    """Aggregate per-account verify-at-seed results into a slot seeding verdict."""
    # bite-axis: all-accounts-verified — any refusal refuses the whole slot.
    if not isinstance(steps, list):
        return _refusal(REFUSAL_SEED_INCOMPLETE)
    if not isinstance(results, dict):
        return _refusal(REFUSAL_SEED_INCOMPLETE)

    planned_accounts = []
    for step in steps:
        if not isinstance(step, dict):
            return _refusal(REFUSAL_SEED_INCOMPLETE)
        account = step.get("account")
        if not isinstance(account, str) or not account:
            return _refusal(REFUSAL_SEED_INCOMPLETE)
        planned_accounts.append(account)

    planned_set = set(planned_accounts)
    if len(planned_accounts) != len(planned_set):
        return _refusal(REFUSAL_SEED_INCOMPLETE)

    result_keys = set(results.keys())
    if result_keys != planned_set:
        return _refusal(REFUSAL_SEED_INCOMPLETE)

    verified_accounts = []
    for account in planned_accounts:
        result = results[account]
        if not isinstance(result, dict):
            return _refusal(REFUSAL_SEED_INCOMPLETE)
        if not result.get("ok"):
            return {
                "ok": False,
                "outcome": OUTCOME_REFUSED,
                "reason": result.get("reason"),
                "account": account,
            }
        verified_accounts.append(account)

    return {
        "ok": True,
        "outcome": OUTCOME_VERIFIED,
        "reason": None,
        "accounts": verified_accounts,
    }


def lapse_disposition(answer, *, reprobe_count):
    """Attended-path lapse rule — parks on confirmed no-session, never remints."""
    # bite-axis: attended lapse — delegate to pilot_identity.lapse_step with sign_in_path attended.
    step = pilot_identity.lapse_step(
        answer,
        sign_in_path="attended",
        reprobe_count=reprobe_count,
    )
    return {
        "outcome": _lapse_outcome(step["action"]),
        "action": step["action"],
        "reason": step["reason"],
    }
