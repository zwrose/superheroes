"""Pilot browser context creation — one context per account with verify-at-seed (C7 / S3).

Non-goals: no browser launch, no capture, no minting — context specs and S3 enforcement only.
"""
import pilot_seed
import pilot_slot

CONTEXT_SCHEMA_VERSION = 1

REFUSAL_OPTIONS_MISMATCH = "context-options-mismatch"
REFUSAL_ARTIFACT_MISSING = "context-artifact-missing"
REFUSAL_ARTIFACT_UNKNOWN_ACCOUNT = "context-artifact-unknown-account"
REFUSAL_SHARED_CONTEXT_REFUSED = "context-shared-context-refused"


class PilotContextError(Exception):
    """Caller or contract refusal from pilot_context."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def context_set(slot, generation, accounts, *, artifacts, capture_surfaces):
    """Build the slot's context set: exactly one context spec per account."""
    try:
        account_set = pilot_slot.slot_account_set(slot, generation, accounts)
    except pilot_slot.PilotSlotError as exc:
        return _refusal(exc.reason)

    slot_ref = account_set["ref"]
    account_list = pilot_slot.account_keys(account_set)

    if not isinstance(artifacts, dict):
        return _refusal(REFUSAL_ARTIFACT_MISSING)

    account_set_keys = set(account_list)
    for account in account_list:
        if account not in artifacts:
            return _refusal(REFUSAL_ARTIFACT_MISSING)

    for account in artifacts:
        if account not in account_set_keys:
            return _refusal(REFUSAL_ARTIFACT_UNKNOWN_ACCOUNT)

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
            artifacts[account],
            capture_surfaces,
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


def context_spec(slot_ref, account, artifact, capture_surfaces, *, requested_options=None):
    """Build one context spec with required capture options and verify-at-seed."""
    # bite-axis: options mismatch — requested_options must equal required_context_options
    # exactly; any deviation refuses context-options-mismatch before seed_request runs.
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
