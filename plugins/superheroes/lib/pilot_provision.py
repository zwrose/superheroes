"""Pilot provisioning — boundary verification and credential authorization (A3).

Ties the pilot framework's target boundary to its policy: runs boundary verification
(including datastore observation), produces the traveling verdict, and gates every
credential-producing call behind that verdict.

The declare-and-exercise and datastore-identity gates are in-process ordering chokepoints,
not sandboxes — launcher, browser, and build session share a UID by design (#660 §14), so
they prevent ordering mistakes, not a hostile process.
"""
import time
from datetime import datetime

import pilot_boundary
import pilot_contract
import pilot_policy
import pilot_seed
import pilot_slot

REFUSAL_SLOT_UNKNOWN = "provision-slot-unknown"
REFUSAL_ACCOUNT_UNKNOWN = "provision-account-unknown"
REFUSAL_MINT_UNSUPPORTED = "provision-mint-unsupported"
REFUSAL_LAUNCH_INVALID = "provision-launch-invalid"
REFUSAL_DECLARATION_KINDS_UNCOVERED = "provision-declaration-kinds-uncovered"
REFUSAL_DECLARATION_SOURCE_MISSING = "provision-declaration-source-missing"
REFUSAL_DATASTORE_IDENTITY_ABSENT = "provision-datastore-identity-absent"
REFUSAL_DATASTORE_IDENTITY_UNMATCHED = "provision-datastore-identity-unmatched"
REFUSAL_DATASTORE_IDENTITY_WEAKER_UNACCEPTED = "provision-datastore-identity-weaker-unaccepted"
REFUSAL_WEAKER_ACCEPTANCE_INVALID = "provision-weaker-acceptance-invalid"
REFUSAL_DATASTORE_IDENTITY_STRENGTH_UNKNOWN = "provision-datastore-identity-strength-unknown"
REFUSAL_MINT_DECLARATION_MISSING = "provision-mint-declaration-missing"

# Re-exported from the one home in `pilot_boundary`, which produces the observations these
# words describe (#866). Kept as module names because callers and tests read them from here.
STRENGTH_STRONG = pilot_boundary.STRENGTH_STRONG
STRENGTH_WEAKER = pilot_boundary.STRENGTH_WEAKER

_WEAKER_ACCEPTANCE_KEYS = frozenset({"acceptedBy", "acceptedAt", "reason"})


class PilotProvisionError(Exception):
    """Provisioning-time refusal."""

    def __init__(self, reason, detail=None):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


def policy_digest(policy):
    """Return the policy declaration digest (A1 reuse)."""
    return pilot_contract.declaration_digest(policy)


def verify_boundary(
    policy,
    slot_ref,
    candidate_target,
    *,
    reach_roots,
    run_cwd,
    app_reported=None,
    candidate_redirects=None,
    verified_at=None,
):
    """Run provisioning-time boundary checks and return a traveling verdict."""
    # bite-axis: boundary verification — target, redirect, and datastore-identity checks assemble a
    # traveling verdict bound to policy digest; assert_results_only refuses material leakage in the
    # verdict.
    try:
        slot, _generation = pilot_slot.parse_slot_ref(slot_ref)
    except pilot_slot.PilotSlotError:
        raise PilotProvisionError(REFUSAL_SLOT_UNKNOWN)
    slot_config = policy.get("slots", {}).get(slot)
    if slot_config is None:
        raise PilotProvisionError(REFUSAL_SLOT_UNKNOWN)

    permitted_redirects = slot_config.get("permittedRedirects", [])
    binding = pilot_boundary.target_binding(
        slot_ref,
        origin=slot_config["origin"],
        permitted_redirects=permitted_redirects,
        protected_targets=policy["protectedTargets"],
    )

    checks = []

    target_result = pilot_boundary.check_target(binding, candidate_target)
    checks.append(("target-binding", target_result))

    redirects = candidate_redirects if candidate_redirects is not None else []
    for redirect in redirects:
        redirect_result = pilot_boundary.check_redirect(binding, redirect)
        checks.append(("redirect-binding", redirect_result))

    observer = policy["datastore"]["observer"]
    if observer is not None:
        try:
            observation = pilot_boundary.observe_datastore_identity(
                observer,
                connection_detail=policy["datastore"]["connectionDetail"],
                reach_roots=reach_roots,
                run_cwd=run_cwd,
            )
            identity_result = pilot_boundary.check_datastore_identity(
                binding,
                observation,
                policy["datastore"]["expectedIdentity"],
            )
            checks.append(("datastore-identity", identity_result))
        except pilot_boundary.PilotBoundaryError as exc:
            checks.append(
                ("datastore-identity", {"ok": False, "reason": exc.reason}),
            )
    elif isinstance(app_reported, str) and app_reported:
        observation = pilot_boundary.app_reported_identity(app_reported)
        identity_result = pilot_boundary.check_datastore_identity(
            binding,
            observation,
            policy["datastore"]["expectedIdentity"],
        )
        checks.append(("datastore-identity", identity_result))
    else:
        checks.append(
            (
                "datastore-identity",
                {
                    "ok": False,
                    "reason": pilot_boundary.REFUSAL_DATASTORE_IDENTITY_UNAVAILABLE,
                },
            ),
        )

    datastore_identity = None
    for _name, result in checks:
        if "provenance" in result:
            datastore_identity = {
                "provenance": result["provenance"],
                "strength": result["strength"],
                "match": result.get("match", False),
            }
            break

    verdict = pilot_boundary.boundary_verdict(
        binding,
        checks=checks,
        policy_digest=policy_digest(policy),
        datastore_identity=datastore_identity,
        verified_at=verified_at,
    )

    pilot_policy.assert_results_only(
        verdict,
        pilot_policy.policy_material(policy),
    )
    return verdict


def _canonical_slot_ref(slot_ref):
    slot, generation = pilot_slot.parse_slot_ref(slot_ref)
    return pilot_slot.format_slot_ref(slot, generation)


def authorized_seed_request(verdict, policy, slot_ref, account, artifact):
    """Authorize and build a seed request descriptor."""
    # bite-axis: seed authorization — passing authorize_credentials gate plus a known account and
    # artifact produce a seed request; neutralizing any gate reddens test_pilot_provision seed paths.
    pilot_boundary.authorize_credentials(
        verdict,
        slot_ref,
        policy_digest(policy),
    )

    slot, _generation = pilot_slot.parse_slot_ref(slot_ref)
    slot_config = policy.get("slots", {}).get(slot)
    if slot_config is None:
        raise PilotProvisionError(REFUSAL_SLOT_UNKNOWN)
    expected_identities = slot_config.get("expectedIdentities", {})
    if account not in expected_identities:
        raise PilotProvisionError(REFUSAL_ACCOUNT_UNKNOWN)

    context_options = pilot_seed.required_context_options(artifact["captureSurfaces"])
    seed_artifact = {
        "path": artifact["path"],
        "expectedUid": artifact["expectedUid"],
        "expectedMode": artifact["expectedMode"],
        "sha256": artifact["sha256"],
    }
    return pilot_seed.seed_request(
        _canonical_slot_ref(slot_ref),
        account,
        seed_artifact,
        context_options,
    )


def authorized_mint_request(verdict, policy, slot_ref, account, envelope):
    """Authorize and build a mint request descriptor."""
    # bite-axis: mint authorization — passing authorize_credentials gate plus an account in
    # mintableAccounts produce a mint request; unsupported mintable list refuses before pilot_seed
    # is reached.
    pilot_boundary.authorize_credentials(
        verdict,
        slot_ref,
        policy_digest(policy),
    )

    slot, _generation = pilot_slot.parse_slot_ref(slot_ref)
    slot_config = policy.get("slots", {}).get(slot)
    if slot_config is None:
        raise PilotProvisionError(REFUSAL_SLOT_UNKNOWN)
    mintable_accounts = slot_config.get("mintableAccounts")
    if not mintable_accounts:
        raise PilotProvisionError(REFUSAL_MINT_UNSUPPORTED)

    return pilot_seed.mint_request(
        account,
        allowlist=mintable_accounts,
        envelope=envelope,
    )


def authorized_app_launch(verdict, policy, slot_ref, launch):
    """Authorize and build an app-launch descriptor bound to the slot's verified origin."""
    # bite-axis: app-launch authorization — passing authorize_credentials gate plus verified
    # baseUrl and readinessUrl on the slot origin produce a launch descriptor; skipping either
    # URL check reddens off-origin readiness tests while baseUrl checks stay green.
    pilot_boundary.authorize_credentials(
        verdict,
        slot_ref,
        policy_digest(policy),
    )

    try:
        slot, _generation = pilot_slot.parse_slot_ref(slot_ref)
    except pilot_slot.PilotSlotError:
        raise PilotProvisionError(REFUSAL_SLOT_UNKNOWN)
    slot_config = policy.get("slots", {}).get(slot)
    if slot_config is None:
        raise PilotProvisionError(REFUSAL_SLOT_UNKNOWN)

    permitted_redirects = slot_config.get("permittedRedirects", [])
    binding = pilot_boundary.target_binding(
        slot_ref,
        origin=slot_config["origin"],
        permitted_redirects=permitted_redirects,
        protected_targets=policy["protectedTargets"],
    )

    if not isinstance(launch, dict):
        raise PilotProvisionError(REFUSAL_LAUNCH_INVALID)

    base_url = launch.get("baseUrl")
    if not isinstance(base_url, str) or not base_url:
        raise PilotProvisionError(REFUSAL_LAUNCH_INVALID)

    readiness_url = launch.get("readinessUrl")
    if not isinstance(readiness_url, str) or not readiness_url:
        raise PilotProvisionError(REFUSAL_LAUNCH_INVALID)

    base_result = pilot_boundary.check_target(binding, base_url)
    if not base_result["ok"]:
        raise PilotProvisionError(base_result["reason"])

    readiness_result = pilot_boundary.check_target(binding, readiness_url)
    if not readiness_result["ok"]:
        raise PilotProvisionError(readiness_result["reason"])

    descriptor = {
        "schemaVersion": 1,
        "slotRef": _canonical_slot_ref(slot_ref),
        "baseUrl": base_url,
        "readinessUrl": readiness_url,
        "policyDigest": policy_digest(policy),
    }

    pilot_policy.assert_results_only(
        descriptor,
        pilot_policy.policy_material(policy),
    )
    return descriptor


def authorized_sentinel_probe_request(verdict, policy, slot_ref, sentinel, envelope):
    """Authorize and build a sentinel probe request descriptor."""
    # bite-axis: sentinel authorization — passing authorize_credentials gate plus a known slot
    # produce a sentinel probe request; credential refusal reddens before
    # pilot_seed.sentinel_probe_request runs.
    pilot_boundary.authorize_credentials(
        verdict,
        slot_ref,
        policy_digest(policy),
    )

    slot, _generation = pilot_slot.parse_slot_ref(slot_ref)
    slot_config = policy.get("slots", {}).get(slot)
    if slot_config is None:
        raise PilotProvisionError(REFUSAL_SLOT_UNKNOWN)
    mintable_accounts = slot_config.get("mintableAccounts", [])
    return pilot_seed.sentinel_probe_request(
        sentinel,
        allowlist=mintable_accounts,
        envelope=envelope,
    )


def _always_applicable(_block, _policy, _slot_ref):
    return True


def _mint_policy_granted(policy, slot_ref):
    try:
        slot, _generation = pilot_slot.parse_slot_ref(slot_ref)
    except pilot_slot.PilotSlotError:
        return False
    slot_config = policy.get("slots", {}).get(slot)
    if slot_config is None:
        return False
    mintable_accounts = slot_config.get("mintableAccounts")
    return bool(mintable_accounts)


def _require_mint_block(block, policy, slot_ref):
    if _mint_policy_granted(policy, slot_ref) and block.get("mint") is None:
        raise PilotProvisionError(REFUSAL_MINT_DECLARATION_MISSING)


def _mint_applicable(block, policy, slot_ref):
    # bite-axis: mint applicability — policy-side mintableAccounts grant makes mint kinds
    # applicable regardless of branch-mutable pilot.mint; block-only trigger is insufficient.
    return _mint_policy_granted(policy, slot_ref) or block.get("mint") is not None


def _extract_identity_probe(block, _policy, _slot_ref):
    return block["identityProbe"]


def _extract_session_surface(block, _policy, _slot_ref):
    return {
        "captureSurface": block["captureSurface"],
        "captureOptions": block["captureOptions"],
    }


def _extract_cleanup_containment(block, _policy, _slot_ref):
    return block["cleanup"]


def _extract_effects_escape(block, _policy, _slot_ref):
    return block["effectsEscape"]


def _extract_operating_ceiling(block, _policy, _slot_ref):
    return {"administrativeMax": block["administrativeMax"]}


def _extract_mint_gate_off(block, policy, slot_ref):
    _require_mint_block(block, policy, slot_ref)
    return block["mint"]["envelope"]


def _extract_mint_account_allowlist(block, policy, slot_ref):
    _require_mint_block(block, policy, slot_ref)
    slot, _generation = pilot_slot.parse_slot_ref(slot_ref)
    return policy["slots"][slot]["mintableAccounts"]


def _extract_app_lifecycle(_block, policy, slot_ref):
    slot, _generation = pilot_slot.parse_slot_ref(slot_ref)
    slot_config = policy["slots"][slot]
    return {
        "origin": slot_config["origin"],
        "permittedRedirects": slot_config["permittedRedirects"],
    }


DECLARATION_SOURCES = {
    "identity-probe": {
        "extract": _extract_identity_probe,
        "applicable": _always_applicable,
    },
    "session-surface": {
        "extract": _extract_session_surface,
        "applicable": _always_applicable,
    },
    "cleanup-containment": {
        "extract": _extract_cleanup_containment,
        "applicable": _always_applicable,
    },
    "effects-escape": {
        "extract": _extract_effects_escape,
        "applicable": _always_applicable,
    },
    "operating-ceiling": {
        "extract": _extract_operating_ceiling,
        "applicable": _always_applicable,
    },
    "mint-gate-off": {
        "extract": _extract_mint_gate_off,
        "applicable": _mint_applicable,
    },
    "mint-account-allowlist": {
        "extract": _extract_mint_account_allowlist,
        "applicable": _mint_applicable,
    },
    "app-lifecycle": {
        "extract": _extract_app_lifecycle,
        "applicable": _always_applicable,
    },
}


def _verify_declaration_sources_complete():
    if set(DECLARATION_SOURCES) != pilot_contract.DECLARATION_KINDS:
        raise PilotProvisionError(REFUSAL_DECLARATION_KINDS_UNCOVERED)


def declaration_for(kind, block, policy, slot_ref):
    """Return whether a declaration kind applies and its current declaration value."""
    if kind not in DECLARATION_SOURCES:
        raise PilotProvisionError(REFUSAL_DECLARATION_KINDS_UNCOVERED)
    entry = DECLARATION_SOURCES[kind]
    applicable = entry["applicable"](block, policy, slot_ref)
    if not applicable:
        return {"applicable": False, "declaration": None}
    try:
        declaration = entry["extract"](block, policy, slot_ref)
    except (KeyError, TypeError, pilot_slot.PilotSlotError):
        raise PilotProvisionError(REFUSAL_DECLARATION_SOURCE_MISSING)
    return {"applicable": True, "declaration": declaration}


def require_declarations_exercised(block, policy, slot_ref, registry):
    """Require every applicable declaration kind to be exercised in the registry."""
    # bite-axis: declare-and-exercise completeness — every DECLARATION_KINDS member must have a
    # DECLARATION_SOURCES entry; divergence refuses provision-declaration-kinds-uncovered.
    _verify_declaration_sources_complete()
    declarations = []
    for kind in sorted(DECLARATION_SOURCES):
        info = declaration_for(kind, block, policy, slot_ref)
        if not info["applicable"]:
            declarations.append({"kind": kind, "status": "not-applicable"})
            continue
        pilot_contract.require_exercised(registry, kind, info["declaration"])
        declarations.append({"kind": kind, "status": "exercised"})
    return declarations


def is_iso8601_utc(value):
    """Return True when ``value`` is an ISO-8601 UTC timestamp with a ``Z`` suffix."""
    if not isinstance(value, str) or not value:
        return False
    text = value.strip()
    if not text.endswith("Z"):
        return False
    try:
        dt = datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError:
        return False
    return dt.tzinfo is not None


def _is_iso8601_utc(value):
    return is_iso8601_utc(value)


def validate_weaker_acceptance(record):
    """Validate a weaker-acceptance record. Raises PilotProvisionError on refusal."""
    if not isinstance(record, dict):
        raise PilotProvisionError(REFUSAL_WEAKER_ACCEPTANCE_INVALID)
    if set(record.keys()) != _WEAKER_ACCEPTANCE_KEYS:
        raise PilotProvisionError(REFUSAL_WEAKER_ACCEPTANCE_INVALID)
    accepted_by = record.get("acceptedBy")
    if not isinstance(accepted_by, str) or not accepted_by:
        raise PilotProvisionError(REFUSAL_WEAKER_ACCEPTANCE_INVALID)
    accepted_at = record.get("acceptedAt")
    if not _is_iso8601_utc(accepted_at):
        raise PilotProvisionError(REFUSAL_WEAKER_ACCEPTANCE_INVALID)
    reason = record.get("reason")
    if not isinstance(reason, str) or not reason:
        raise PilotProvisionError(REFUSAL_WEAKER_ACCEPTANCE_INVALID)
    return {
        "acceptedBy": accepted_by,
        "acceptedAt": accepted_at,
        "reason": reason,
    }


_validate_weaker_acceptance = validate_weaker_acceptance


def gate_datastore_identity(verdict, *, weaker_acceptance=None):
    """Gate provisioning on datastore identity strength and weaker acceptance.

    This is an in-process ordering chokepoint, not a sandbox — launcher, browser, and build
    session share a UID by design (#660 §14), so it prevents ordering mistakes, not a hostile
    process.
    """
    # bite-axis: datastore identity strength — weaker strength refuses unless a valid acceptance
    # record is supplied; absent or invalid identity refuses before provisioning proceeds.
    identity = verdict.get("datastoreIdentity") if isinstance(verdict, dict) else None
    if not isinstance(identity, dict):
        raise PilotProvisionError(REFUSAL_DATASTORE_IDENTITY_ABSENT)
    provenance = identity.get("provenance")
    strength = identity.get("strength")
    match = identity.get("match")
    if not isinstance(provenance, str) or not provenance:
        raise PilotProvisionError(REFUSAL_DATASTORE_IDENTITY_ABSENT)
    if not isinstance(strength, str) or not strength:
        raise PilotProvisionError(REFUSAL_DATASTORE_IDENTITY_ABSENT)
    if type(match) is not bool:
        raise PilotProvisionError(REFUSAL_DATASTORE_IDENTITY_ABSENT)
    if match is not True:
        raise PilotProvisionError(REFUSAL_DATASTORE_IDENTITY_UNMATCHED)
    if strength == STRENGTH_STRONG:
        return {
            "ok": True,
            "reason": None,
            "strength": strength,
            "provenance": provenance,
            "acceptance": None,
        }
    if strength == STRENGTH_WEAKER:
        if weaker_acceptance is None:
            raise PilotProvisionError(REFUSAL_DATASTORE_IDENTITY_WEAKER_UNACCEPTED)
        acceptance = _validate_weaker_acceptance(weaker_acceptance)
        return {
            "ok": True,
            "reason": None,
            "strength": strength,
            "provenance": provenance,
            "acceptance": acceptance,
        }
    raise PilotProvisionError(REFUSAL_DATASTORE_IDENTITY_STRENGTH_UNKNOWN)


def gate_provisioning(verdict, policy, slot_ref, block, registry, *, weaker_acceptance=None):
    """Compose boundary authorization, identity strength, and declare-and-exercise gates."""
    # bite-axis: provisioning composition — authorize_credentials must run before identity and
    # declaration gates; assert_results_only refuses policy material in the receipt.
    pilot_boundary.authorize_credentials(verdict, slot_ref, policy_digest(policy))
    identity_gate = gate_datastore_identity(verdict, weaker_acceptance=weaker_acceptance)
    declarations = require_declarations_exercised(block, policy, slot_ref, registry)
    slot, generation = pilot_slot.parse_slot_ref(slot_ref)
    canonical_slot_ref = pilot_slot.format_slot_ref(slot, generation)
    receipt = {
        "slotRef": canonical_slot_ref,
        "policyDigest": policy_digest(policy),
        "datastoreIdentity": {
            "provenance": identity_gate["provenance"],
            "strength": identity_gate["strength"],
            "match": True,
        },
        "weakerAcceptance": identity_gate["acceptance"],
        "declarations": declarations,
        "gatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    pilot_policy.assert_results_only(
        receipt,
        pilot_policy.policy_material(policy),
    )
    return receipt
