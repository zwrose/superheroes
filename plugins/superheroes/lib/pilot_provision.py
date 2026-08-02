"""Pilot provisioning — boundary verification and credential authorization (A3).

Ties the pilot framework's target boundary to its policy: runs boundary verification
(including datastore observation), produces the traveling verdict, and gates every
credential-producing call behind that verdict.
"""
import pilot_boundary
import pilot_contract
import pilot_policy
import pilot_seed
import pilot_slot

REFUSAL_SLOT_UNKNOWN = "provision-slot-unknown"
REFUSAL_ACCOUNT_UNKNOWN = "provision-account-unknown"
REFUSAL_MINT_UNSUPPORTED = "provision-mint-unsupported"


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
    slot, _generation = pilot_slot.parse_slot_ref(slot_ref)
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
    pilot_boundary.authorize_credentials(
        verdict,
        slot_ref,
        policy_digest(policy),
    )

    slot, _generation = pilot_slot.parse_slot_ref(slot_ref)
    expected_identities = policy["slots"][slot].get("expectedIdentities", {})
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
    pilot_boundary.authorize_credentials(
        verdict,
        slot_ref,
        policy_digest(policy),
    )

    slot, _generation = pilot_slot.parse_slot_ref(slot_ref)
    mintable_accounts = policy["slots"][slot].get("mintableAccounts")
    if not mintable_accounts:
        raise PilotProvisionError(REFUSAL_MINT_UNSUPPORTED)

    return pilot_seed.mint_request(
        account,
        allowlist=mintable_accounts,
        envelope=envelope,
    )


def authorized_sentinel_probe_request(verdict, policy, slot_ref, sentinel, envelope):
    """Authorize and build a sentinel probe request descriptor."""
    pilot_boundary.authorize_credentials(
        verdict,
        slot_ref,
        policy_digest(policy),
    )

    slot, _generation = pilot_slot.parse_slot_ref(slot_ref)
    mintable_accounts = policy["slots"][slot].get("mintableAccounts", [])
    return pilot_seed.sentinel_probe_request(
        sentinel,
        allowlist=mintable_accounts,
        envelope=envelope,
    )
