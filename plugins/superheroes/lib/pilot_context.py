"""Pilot browser context creation — one context per account with verify-at-seed (C7 / S3).

Non-goals: no browser launch, no capture, no minting — context specs and S3 enforcement only.
"""
import pilot_contract
import pilot_seed
import pilot_slot

CONTEXT_SCHEMA_VERSION = 1

REFUSAL_OPTIONS_MISMATCH = "context-options-mismatch"
REFUSAL_ARTIFACT_MISSING = "context-artifact-missing"
REFUSAL_ARTIFACT_UNKNOWN_ACCOUNT = "context-artifact-unknown-account"
REFUSAL_SHARED_CONTEXT_REFUSED = "context-shared-context-refused"
REFUSAL_PROVISIONING_RECEIPT_MISSING = "context-provisioning-receipt-missing"
REFUSAL_PROVISIONING_RECEIPT_INVALID = "context-provisioning-receipt-invalid"
REFUSAL_PROVISIONING_RECEIPT_SLOT_MISMATCH = "context-provisioning-receipt-slot-mismatch"
REFUSAL_SIGN_IN_PATH_INVALID = "context-sign-in-path-invalid"
REFUSAL_ARTIFACT_REFUSED_ON_LIVE_SEEDING = "context-artifact-refused-on-live-seeding"

_PROVISIONING_RECEIPT_KEYS = frozenset(
    {"slotRef", "policyDigest", "datastoreIdentity", "declarations"},
)


def context_set(
    slot,
    generation,
    accounts,
    *,
    sign_in_path,
    artifacts=None,
    capture_surfaces,
    provisioning_receipt,
):
    """Build the slot's context set: exactly one context spec per account."""
    try:
        account_set = pilot_slot.slot_account_set(slot, generation, accounts)
    except pilot_slot.PilotSlotError as exc:
        return _refusal(exc.reason)

    slot_ref = account_set["ref"]
    account_list = pilot_slot.account_keys(account_set)

    if sign_in_path not in pilot_contract.SIGN_IN_PATHS:
        return _refusal(REFUSAL_SIGN_IN_PATH_INVALID)

    if artifacts is not None:
        return _refusal(REFUSAL_ARTIFACT_REFUSED_ON_LIVE_SEEDING)

    contexts = []
    seen_identities = set()
    for account in account_list:
        identity = _context_identity(slot_ref, account)
        if identity in seen_identities:
            return _refusal(REFUSAL_SHARED_CONTEXT_REFUSED)
        seen_identities.add(identity)

        result = context_spec(
            slot_ref,
            account,
            capture_surfaces,
            provisioning_receipt=provisioning_receipt,
            sign_in_path=sign_in_path,
        )
        if not result["ok"]:
            return _refusal(result["reason"])
        contexts.append(_spec_from_context_result(result))

    return {
        "ok": True,
        "reason": None,
        "slotRef": slot_ref,
        "contexts": contexts,
    }


def context_spec(
    slot_ref,
    account,
    capture_surfaces,
    *,
    provisioning_receipt,
    sign_in_path,
    artifact=None,
    requested_options=None,
):
    """Build one context spec with required capture options for live seeding."""
    # bite-axis: provisioning receipt — context creation requires a valid gate_provisioning
    # receipt before seeding runs; missing or invalid receipt refuses before sign-in-path
    # and artifact checks.
    receipt_refusal = _validate_provisioning_receipt(provisioning_receipt, slot_ref)
    if receipt_refusal is not None:
        return _refusal(receipt_refusal)

    if sign_in_path not in pilot_contract.SIGN_IN_PATHS:
        return _refusal(REFUSAL_SIGN_IN_PATH_INVALID)

    # bite-axis: live-seeding paths refuse a supplied artifact — artifact presence must not
    # infer attended/minted mode; a broken restore call must not silently become live seeding.
    if artifact is not None:
        return _refusal(REFUSAL_ARTIFACT_REFUSED_ON_LIVE_SEEDING)

    # bite-axis: options mismatch — requested_options must equal required_context_options
    # exactly; any deviation refuses context-options-mismatch before options are returned.
    try:
        required_options = pilot_seed.required_context_options(capture_surfaces)
    except pilot_seed.PilotSeedError as exc:
        return _refusal(exc.reason)

    if requested_options is not None:
        if requested_options != required_options:
            return _refusal(REFUSAL_OPTIONS_MISMATCH)
        options = requested_options
    else:
        options = required_options

    return {
        "ok": True,
        "reason": None,
        "schemaVersion": CONTEXT_SCHEMA_VERSION,
        "slotRef": slot_ref,
        "account": account,
        "contextOptions": options,
        "artifact": None,
        "captureSurfaces": list(capture_surfaces),
    }


def context_spec_from_artifact(
    slot_ref,
    account,
    artifact,
    capture_surfaces,
    *,
    provisioning_receipt,
    requested_options=None,
):
    """Build one context spec from a stored artifact via verify-at-seed (latent S3 restore seam).

    No caller in this repository invokes this entry point today — it is kept as the declared
    artifact-restore path for a future restore flow. It is not reachable by passing
    ``sign_in_path`` on ``context_spec``.
    """
    receipt_refusal = _validate_provisioning_receipt(provisioning_receipt, slot_ref)
    if receipt_refusal is not None:
        return _refusal(receipt_refusal)

    if artifact is None:
        return _refusal(REFUSAL_ARTIFACT_MISSING)

    try:
        required_options = pilot_seed.required_context_options(capture_surfaces)
    except pilot_seed.PilotSeedError as exc:
        return _refusal(exc.reason)

    if requested_options is not None:
        if requested_options != required_options:
            return _refusal(REFUSAL_OPTIONS_MISMATCH)
        options = requested_options
    else:
        options = required_options

    try:
        seed_result = pilot_seed.seed_request(slot_ref, account, artifact, options)
    except pilot_seed.PilotSeedError as exc:
        return _refusal(exc.reason)

    return {
        "ok": True,
        "reason": None,
        "schemaVersion": CONTEXT_SCHEMA_VERSION,
        "slotRef": seed_result["slotRef"],
        "account": seed_result["account"],
        "contextOptions": seed_result["contextOptions"],
        "artifact": seed_result["artifact"],
        "captureSurfaces": list(capture_surfaces),
    }


def _validate_provisioning_receipt(receipt, slot_ref):
    """Structural check of a provisioning receipt; no pilot_provision import."""
    if receipt is None:
        return REFUSAL_PROVISIONING_RECEIPT_MISSING
    if not isinstance(receipt, dict):
        return REFUSAL_PROVISIONING_RECEIPT_INVALID
    if set(receipt.keys()) < _PROVISIONING_RECEIPT_KEYS:
        return REFUSAL_PROVISIONING_RECEIPT_INVALID
    for key in _PROVISIONING_RECEIPT_KEYS:
        value = receipt.get(key)
        if value is None:
            return REFUSAL_PROVISIONING_RECEIPT_INVALID
        if key == "datastoreIdentity":
            if not isinstance(value, dict):
                return REFUSAL_PROVISIONING_RECEIPT_INVALID
            provenance = value.get("provenance")
            strength = value.get("strength")
            match = value.get("match")
            if not isinstance(provenance, str) or not provenance:
                return REFUSAL_PROVISIONING_RECEIPT_INVALID
            if not isinstance(strength, str) or not strength:
                return REFUSAL_PROVISIONING_RECEIPT_INVALID
            if match is not True:
                return REFUSAL_PROVISIONING_RECEIPT_INVALID
        elif key == "declarations":
            if not isinstance(value, list) or not value:
                return REFUSAL_PROVISIONING_RECEIPT_INVALID
            for entry in value:
                if not isinstance(entry, dict):
                    return REFUSAL_PROVISIONING_RECEIPT_INVALID
                kind = entry.get("kind")
                status = entry.get("status")
                if not isinstance(kind, str) or not kind:
                    return REFUSAL_PROVISIONING_RECEIPT_INVALID
                if not isinstance(status, str) or not status:
                    return REFUSAL_PROVISIONING_RECEIPT_INVALID
        elif not isinstance(value, str) or not value:
            return REFUSAL_PROVISIONING_RECEIPT_INVALID
    try:
        slot, generation = pilot_slot.parse_slot_ref(slot_ref)
        canonical_slot_ref = pilot_slot.format_slot_ref(slot, generation)
    except pilot_slot.PilotSlotError:
        return REFUSAL_PROVISIONING_RECEIPT_SLOT_MISMATCH
    if receipt["slotRef"] != canonical_slot_ref:
        return REFUSAL_PROVISIONING_RECEIPT_SLOT_MISMATCH
    return None


def _context_identity(slot_ref, account):
    """Return a hashable identity for one browser context within a slot."""
    return (slot_ref, account)


def _spec_from_context_result(result):
    return {
        "schemaVersion": result["schemaVersion"],
        "slotRef": result["slotRef"],
        "account": result["account"],
        "contextOptions": result["contextOptions"],
        "artifact": result["artifact"],
        "captureSurfaces": result["captureSurfaces"],
    }


def _refusal(reason):
    return {"ok": False, "reason": reason}
