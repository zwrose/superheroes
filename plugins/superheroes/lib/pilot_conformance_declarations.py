"""Conformance declaration rows — attested vs exercised coverage per slot (C10).

Enumerates every declaration kind against every policy slot and grades registry
receipts without conflating prior exercise with configure-time coverage.
"""
import pilot_contract
import pilot_policy
import pilot_provision
import pilot_slot

SCHEMA = 1

STATUS_ATTESTED = "attested"
STATUS_ABSENT = "absent"
STATUS_NOT_APPLICABLE = "not-applicable"
DECLARATION_STATUSES = frozenset({
    STATUS_ATTESTED,
    STATUS_ABSENT,
    STATUS_NOT_APPLICABLE,
})

REASON_ROW_RAISED = "conformance-declaration-row-raised"
REASON_DECLARATION_UNEXERCISED = pilot_contract.REFUSAL_DECLARATION_UNEXERCISED
_REASON_TOKEN_MAX_LEN = 64

_ROW_KEYS = frozenset({
    "kind",
    "slotRef",
    "status",
    "declarationDigest",
    "reason",
})

# Policy slots carry slot ids only; generation is runtime lifecycle state. Generation 1 is the
# minimum valid value format_slot_ref accepts and is the canonical reporting generation when
# enumerating policy slot keys that carry no generation.
_REPORTING_GENERATION = 1


def _normalize_row_reason(exc):
    reason = getattr(exc, "reason", None)
    if (
        isinstance(reason, str)
        and reason
        and not any(ch.isspace() for ch in reason)
        and len(reason) <= _REASON_TOKEN_MAX_LEN
    ):
        return reason
    return REASON_ROW_RAISED


def _slot_ref_for_policy_slot(slot_name):
    return pilot_slot.format_slot_ref(slot_name, _REPORTING_GENERATION)


def _build_row(kind, slot_ref, info, registry):
    if not info["applicable"]:
        return {
            "kind": kind,
            "slotRef": slot_ref,
            "status": STATUS_NOT_APPLICABLE,
            "declarationDigest": None,
            "reason": None,
        }

    declaration = info["declaration"]
    digest = pilot_contract.declaration_digest(declaration)
    # bite-axis: attested not exercised — registry match reports attested, never exercised.
    if pilot_contract.is_exercised(registry, kind, declaration):
        return {
            "kind": kind,
            "slotRef": slot_ref,
            "status": STATUS_ATTESTED,
            "declarationDigest": digest,
            "reason": None,
        }

    # bite-axis: unexercised applicable — absent with pilot-declaration-unexercised.
    return {
        "kind": kind,
        "slotRef": slot_ref,
        "status": STATUS_ABSENT,
        "declarationDigest": digest,
        "reason": REASON_DECLARATION_UNEXERCISED,
    }


def declaration_rows(block, policy, registry, *, now):
    """Return one row per (kind, slot, digest) across every slot in the policy."""
    del now  # reserved for future freshness checks; rows are point-in-time from inputs.
    pilot_provision._verify_declaration_sources_complete()
    slots = policy.get("slots") if isinstance(policy, dict) else None
    if not isinstance(slots, dict):
        return []

    rows = []
    for slot_name in sorted(slots):
        slot_ref = _slot_ref_for_policy_slot(slot_name)
        for kind in sorted(pilot_provision.DECLARATION_SOURCES):
            try:
                info = pilot_provision.declaration_for(kind, block, policy, slot_ref)
            except pilot_provision.PilotProvisionError as exc:
                # bite-axis: provision refusal — never propagate; surface refusal token on row.
                rows.append({
                    "kind": kind,
                    "slotRef": slot_ref,
                    "status": STATUS_ABSENT,
                    "declarationDigest": None,
                    "reason": exc.reason,
                })
                continue
            except Exception as exc:
                # bite-axis: row isolation — one bad row must not blank the report.
                rows.append({
                    "kind": kind,
                    "slotRef": slot_ref,
                    "status": STATUS_ABSENT,
                    "declarationDigest": None,
                    "reason": _normalize_row_reason(exc),
                })
                continue
            try:
                rows.append(_build_row(kind, slot_ref, info, registry))
            except Exception as exc:
                rows.append({
                    "kind": kind,
                    "slotRef": slot_ref,
                    "status": STATUS_ABSENT,
                    "declarationDigest": None,
                    "reason": _normalize_row_reason(exc),
                })

    material = pilot_policy.policy_material(policy)
    pilot_policy.assert_results_only(rows, material)
    for row in rows:
        if set(row.keys()) != _ROW_KEYS:
            raise ValueError("declaration row shape invalid")
    return rows


def declarations_block(block, policy, registry, *, now):
    """Return the `declarations` envelope: schemaVersion, rows, and counts."""
    rows = declaration_rows(block, policy, registry, now=now)
    attested = sum(1 for row in rows if row["status"] == STATUS_ATTESTED)
    absent = sum(1 for row in rows if row["status"] == STATUS_ABSENT)
    not_applicable = sum(1 for row in rows if row["status"] == STATUS_NOT_APPLICABLE)
    # bite-axis: vacuous pass refusal — empty row list is never ok.
    ok = bool(rows) and absent == 0
    return {
        "schemaVersion": SCHEMA,
        "rows": rows,
        "attested": attested,
        "absent": absent,
        "notApplicable": not_applicable,
        "ok": ok,
    }
