"""Pilot slot identity, generation, and account-set types.

Slot references use ``<slot>@<generation>`` where ``slot`` matches ``store.SLOT_RE``
and ``generation`` is a decimal integer >= 1 with no leading zeros.

Round-trip guarantee: ``parse_slot_ref(format_slot_ref(s, g)) == (s, g)`` for every
valid ``(s, g)``.

Non-goals (owned by later sub-issues): no allocation, no incrementing, no staleness
comparison, no fencing, no quarantine — those belong to A2a and C7.
"""
from store import SLOT_RE

REFUSAL_SLOT_ID_INVALID = "slot-id-invalid"
REFUSAL_GENERATION_INVALID = "slot-generation-invalid"
REFUSAL_SLOT_REF_MALFORMED = "slot-ref-malformed"
REFUSAL_ACCOUNT_SET_EMPTY = "slot-account-set-empty"
REFUSAL_ACCOUNT_DUPLICATE = "slot-account-duplicate"
REFUSAL_ACCOUNT_ROLE_MISSING = "slot-account-role-missing"
REFUSAL_ACCOUNT_ENTRY_INVALID = "slot-account-entry-invalid"


class PilotSlotError(Exception):
    """Raised when slot identity, generation, or account-set validation fails."""

    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def validate_slot_id(slot):
    """Return ``slot`` when it is a ``str`` matching ``SLOT_RE``; refuse otherwise."""
    if not isinstance(slot, str) or not SLOT_RE.match(slot):
        raise PilotSlotError(reason=REFUSAL_SLOT_ID_INVALID)
    return slot


def validate_generation(generation):
    """Return ``generation`` when it is an ``int`` (not ``bool``) >= 1; refuse otherwise."""
    if not isinstance(generation, int) or isinstance(generation, bool) or generation < 1:
        raise PilotSlotError(reason=REFUSAL_GENERATION_INVALID)
    return generation


def format_slot_ref(slot, generation):
    """Return ``"<slot>@<generation>"`` after validating both halves."""
    slot = validate_slot_id(slot)
    generation = validate_generation(generation)
    return "%s@%d" % (slot, generation)


def parse_slot_ref(ref):
    """Parse ``"<slot>@<generation>"`` into ``(slot, generation)``."""
    if not isinstance(ref, str):
        raise PilotSlotError(reason=REFUSAL_SLOT_REF_MALFORMED)
    if "@" not in ref:
        raise PilotSlotError(reason=REFUSAL_SLOT_REF_MALFORMED)
    slot_part, sep, generation_part = ref.partition("@")
    if sep != "@" or "@" in generation_part:
        raise PilotSlotError(reason=REFUSAL_SLOT_REF_MALFORMED)
    if not slot_part or not generation_part:
        raise PilotSlotError(reason=REFUSAL_SLOT_REF_MALFORMED)
    if not generation_part.isascii() or not generation_part.isdigit():
        raise PilotSlotError(reason=REFUSAL_SLOT_REF_MALFORMED)
    if len(generation_part) > 1 and generation_part[0] == "0":
        raise PilotSlotError(reason=REFUSAL_SLOT_REF_MALFORMED)
    slot = validate_slot_id(slot_part)
    generation = int(generation_part)
    if generation < 1:
        raise PilotSlotError(reason=REFUSAL_GENERATION_INVALID)
    return slot, generation


def _validate_account_entry(entry):
    if not isinstance(entry, dict):
        raise PilotSlotError(reason=REFUSAL_ACCOUNT_ENTRY_INVALID)
    account = entry.get("account")
    role = entry.get("role")
    if not isinstance(account, str) or not account:
        raise PilotSlotError(reason=REFUSAL_ACCOUNT_ENTRY_INVALID)
    if "role" not in entry or not isinstance(role, str) or not role:
        raise PilotSlotError(reason=REFUSAL_ACCOUNT_ROLE_MISSING)
    return account, role


def slot_account_set(slot, generation, accounts):
    """Build a validated slot account-set dict with a fresh accounts list."""
    slot = validate_slot_id(slot)
    generation = validate_generation(generation)
    if not accounts:
        raise PilotSlotError(reason=REFUSAL_ACCOUNT_SET_EMPTY)
    seen = set()
    validated_accounts = []
    for entry in accounts:
        account, role = _validate_account_entry(entry)
        if account in seen:
            raise PilotSlotError(reason=REFUSAL_ACCOUNT_DUPLICATE)
        seen.add(account)
        validated_accounts.append({"account": account, "role": role})
    return {
        "slot": slot,
        "generation": generation,
        "ref": format_slot_ref(slot, generation),
        "accounts": validated_accounts,
    }


def account_keys(slot_account_set_dict):
    """Return account keys from a slot account-set dict in declaration order."""
    return [entry["account"] for entry in slot_account_set_dict["accounts"]]
