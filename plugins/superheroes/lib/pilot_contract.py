"""Pilot block contract validator and declare-and-exercise registry (A1).

Every pilot declaration must be exercised before the engine treats it as present.
Records are bound to a digest of the exact declaration they exercised, so changing
the probe, cleanup command, account set, or mint envelope invalidates the old
receipt rather than inheriting it.

Non-goals (§S6): policy document resolution (A3), generation allocation (A2a).
"""
import hashlib
import json
import re
import unicodedata

import pilot_probe
import pilot_seed

PILOT_BLOCK_KEY = "pilot"
PILOT_SCHEMA_VERSION = 1
REGISTRY_SCHEMA_VERSION = 1

SIGN_IN_PATHS = frozenset({"attended", "minted"})
ATTENDED_VEHICLES = frozenset({"automation", "real-chrome"})

_SIGN_IN_PATH_REQUIRED_BLOCK = {
    "attended": "attended",
    "minted": "mint",
}
VALIDITY_PROVENANCE = frozenset({
    "cookie-expiry",
    "token-claim",
    "server-probe",
    "unknown",
})
DECLARATION_KINDS = frozenset({
    "identity-probe",
    "session-surface",
    "cleanup-containment",
    "mint-gate-off",
    "mint-account-allowlist",
    "effects-escape",
    "operating-ceiling",
    "app-lifecycle",
})

# The one home for the `{namespace}` placeholder: this module validates it on the declared
# cleanup command, and `pilot_policy` / `pilot_cleanup` read it from here rather than
# respelling the literal (#866).
NAMESPACE_PLACEHOLDER = "{namespace}"
PLACEHOLDER_RE = re.compile(r"\{[^{}]*\}")

REFUSAL_SCHEMA_VERSION_UNSUPPORTED = "pilot-schema-version-unsupported"
REFUSAL_SIGN_IN_PATH_INVALID = "pilot-sign-in-path-invalid"
REFUSAL_SIGN_IN_PATH_RETIRED_CAPTURED = "pilot-sign-in-path-retired-captured"
REFUSAL_SIGN_IN_PATH_UNHANDLED = "pilot-sign-in-path-unhandled"
REFUSAL_ATTENDED_DECLARATION_MISSING = "pilot-attended-declaration-missing"
REFUSAL_ATTENDED_DECLARATION_INVALID = "pilot-attended-declaration-invalid"
REFUSAL_ATTENDED_VEHICLE_INVALID = "pilot-attended-vehicle-invalid"
REFUSAL_CREDENTIAL_SET_EMPTY = "pilot-credential-set-empty"
REFUSAL_CREDENTIAL_SET_INVALID = "pilot-credential-set-invalid"
REFUSAL_ACCOUNT_KEY_DUPLICATE = "pilot-account-key-duplicate"
REFUSAL_ACCOUNT_KEY_INVALID = "pilot-account-key-invalid"
REFUSAL_ACCOUNT_ROLE_MISSING = "pilot-account-role-missing"
REFUSAL_EXPECTED_IDENTITY_INLINE_REFUSED = "pilot-expected-identity-inline-refused"
REFUSAL_CAPTURE_SURFACE_INVALID = "pilot-capture-surface-invalid"
REFUSAL_CAPTURE_SURFACE_SESSION_STORAGE = "pilot-capture-surface-session-storage-refused"
REFUSAL_CAPTURE_OPTIONS_INVALID = "pilot-capture-options-invalid"
REFUSAL_CAPTURE_OPTIONS_MISMATCH = "pilot-capture-options-mismatch"
REFUSAL_VALIDITY_PROVENANCE_INVALID = "pilot-validity-provenance-invalid"
REFUSAL_IDENTITY_PROBE_INVALID = "pilot-identity-probe-invalid"
REFUSAL_IDENTITY_PROBE_EXPECTATION_UNKNOWN = "pilot-identity-probe-expectation-unknown"
REFUSAL_CLEANUP_COMMAND_INVALID = "pilot-cleanup-command-invalid"
REFUSAL_CLEANUP_UNPARAMETERIZED = "pilot-cleanup-unparameterized"
REFUSAL_CLEANUP_PLACEHOLDER_IN_ARGV0 = "pilot-cleanup-placeholder-in-argv0"
REFUSAL_ADMINISTRATIVE_MAX_INVALID = "pilot-administrative-max-invalid"
REFUSAL_EFFECTS_ESCAPE_ABSENT = "pilot-effects-escape-absent"
REFUSAL_EFFECTS_ESCAPE_INVALID = "pilot-effects-escape-invalid"
REFUSAL_EFFECTS_ESCAPE_EVIDENCE_MISSING = "pilot-effects-escape-evidence-missing"
REFUSAL_POLICY_REF_MISSING = "pilot-policy-ref-missing"
REFUSAL_MINT_DECLARATION_MISSING = "pilot-mint-declaration-missing"
REFUSAL_MINTABLE_ALLOWLIST_INLINE_REFUSED = "pilot-mintable-allowlist-inline-refused"
REFUSAL_MINT_ENVELOPE_INCOMPLETE = "pilot-mint-envelope-incomplete"
REFUSAL_MINT_ENVELOPE_SCOPE_CONFLICT = "pilot-mint-envelope-scope-conflict"
REFUSAL_MINT_GATE_OFF_TEST_MISSING = "pilot-mint-gate-off-test-missing"
REFUSAL_MINT_SENTINEL_MISSING = "pilot-mint-sentinel-missing"
REFUSAL_UNKNOWN_FIELD = "pilot-unknown-field"
REFUSAL_DECLARATION_UNEXERCISED = "pilot-declaration-unexercised"
REFUSAL_DECLARATION_KIND_UNKNOWN = "pilot-declaration-kind-unknown"

_PILOT_TOP_KEYS = frozenset({
    "schemaVersion",
    "signInPath",
    "credentialSet",
    "captureSurface",
    "captureOptions",
    "validityProvenance",
    "identityProbe",
    "cleanup",
    "administrativeMax",
    "effectsEscape",
    "policyRef",
    "mint",
    "attended",
})
_CREDENTIAL_ENTRY_KEYS = frozenset({"account", "role"})
_IDENTITY_PROBE_KEYS = frozenset({"path", "unseededExpectation"})
_CLEANUP_KEYS = frozenset({"command"})
_EFFECTS_ESCAPE_KEYS = frozenset({"canEscape", "evidence"})
_POLICY_REF_KEYS = frozenset({"declaration"})
_MINT_KEYS = frozenset({"envelope", "sentinelIdentifier"})
_ATTENDED_KEYS = frozenset({"vehicle"})
_MINT_ENVELOPE_KEYS = frozenset({
    "enablingFlagEnvVar",
    "enabledScopes",
    "forbiddenScopes",
    "gateOffTestCommand",
})
_CAPTURE_OPTION_KEYS = frozenset({"indexedDB", "credentials"})

_SEED_SURFACE_REFUSALS = {
    pilot_seed.REFUSAL_SESSION_STORAGE: REFUSAL_CAPTURE_SURFACE_SESSION_STORAGE,
    pilot_seed.REFUSAL_SURFACE_UNKNOWN: REFUSAL_CAPTURE_SURFACE_INVALID,
    pilot_seed.REFUSAL_SURFACES_INVALID: REFUSAL_CAPTURE_SURFACE_INVALID,
    pilot_seed.REFUSAL_SURFACES_EMPTY: REFUSAL_CAPTURE_SURFACE_INVALID,
    pilot_seed.REFUSAL_SURFACE_DUPLICATE: REFUSAL_CAPTURE_SURFACE_INVALID,
}


class PilotContractError(Exception):
    """Pilot block or registry refusal."""

    def __init__(self, reason, path):
        super().__init__(reason)
        self.reason = reason
        self.path = path


def validate_config(cfg):
    """Structural validation of cfg['pilot'] when present; no-op when absent.

    Declare-and-exercise is enforced by the provisioning caller (C7), which
    holds the registry outside this process's reach — do not wire a registry here.
    """
    if not isinstance(cfg, dict):
        raise PilotContractError(REFUSAL_UNKNOWN_FIELD, "")
    if PILOT_BLOCK_KEY not in cfg:
        return
    block = cfg[PILOT_BLOCK_KEY]
    if not isinstance(block, dict):
        raise PilotContractError(REFUSAL_UNKNOWN_FIELD, PILOT_BLOCK_KEY)
    validate_pilot_block(block)


def validate_pilot_block(block):
    """Structural validation only; raise PilotContractError on the first refusal.

    The declare-and-exercise gate is enforced by the provisioning caller, which
    holds the registry, because the registry is deliberately outside this process's
    reach.
    """
    if not isinstance(block, dict):
        raise PilotContractError(REFUSAL_UNKNOWN_FIELD, PILOT_BLOCK_KEY)
    _check_unknown_keys(block, _PILOT_TOP_KEYS, PILOT_BLOCK_KEY)
    _validate_schema_version(block)
    sign_in_path = _validate_sign_in_path(block)
    _validate_credential_set(block)
    _validate_capture_surface_and_options(block)
    _validate_validity_provenance(block)
    _validate_identity_probe(block)
    _validate_cleanup(block)
    _validate_administrative_max(block)
    _validate_effects_escape(block)
    _validate_policy_ref(block)
    _validate_attended(block, sign_in_path)
    _validate_mint(block, sign_in_path)


def supports_unattended_horizon(provenance):
    """True when validity provenance supports unattended horizon; False for unknown."""
    if provenance not in VALIDITY_PROVENANCE:
        raise ValueError("unknown validity provenance: %r" % (provenance,))
    return provenance != "unknown"


def declaration_digest(declaration):
    """SHA-256 digest (first 16 hex chars) of NFC-normalized declaration JSON."""
    normalized = _nfc_normalize(declaration)
    payload = json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def is_exercised(registry, kind, declaration):
    """True when registry holds a matching exercised declaration record."""
    if kind not in DECLARATION_KINDS:
        raise PilotContractError(REFUSAL_DECLARATION_KIND_UNKNOWN, kind)
    if not isinstance(registry, dict):
        return False
    registry_version = registry.get("schemaVersion")
    if type(registry_version) is not int or registry_version != REGISTRY_SCHEMA_VERSION:
        return False
    records = registry.get("records")
    if not isinstance(records, list):
        return False
    digest = declaration_digest(declaration)
    for record in records:
        if not isinstance(record, dict):
            continue
        if record.get("kind") != kind:
            continue
        if record.get("declarationDigest") != digest:
            continue
        exercised_at = record.get("exercisedAt")
        if not isinstance(exercised_at, str) or not exercised_at:
            continue
        receipt = record.get("receipt")
        if not isinstance(receipt, dict):
            continue
        if receipt.get("result") != "pass":
            continue
        evidence = receipt.get("evidence")
        if not isinstance(evidence, str) or not evidence:
            continue
        return True
    return False


def require_exercised(registry, kind, declaration):
    """Raise when the declaration has not been exercised."""
    if kind not in DECLARATION_KINDS:
        raise PilotContractError(REFUSAL_DECLARATION_KIND_UNKNOWN, kind)
    if not is_exercised(registry, kind, declaration):
        raise PilotContractError(REFUSAL_DECLARATION_UNEXERCISED, kind)


def _validate_schema_version(block):
    version = block.get("schemaVersion")
    if type(version) is not int or version != PILOT_SCHEMA_VERSION:
        raise PilotContractError(
            REFUSAL_SCHEMA_VERSION_UNSUPPORTED,
            "pilot.schemaVersion",
        )


def _verify_sign_in_path_required_block_complete():
    if set(_SIGN_IN_PATH_REQUIRED_BLOCK) != SIGN_IN_PATHS:
        raise ValueError("sign-in path required-block mapping incomplete")


def _required_block_key(sign_in_path):
    if sign_in_path not in _SIGN_IN_PATH_REQUIRED_BLOCK:
        raise PilotContractError(REFUSAL_SIGN_IN_PATH_UNHANDLED, "pilot.signInPath")
    return _SIGN_IN_PATH_REQUIRED_BLOCK[sign_in_path]


def _validate_sign_in_path(block):
    sign_in_path = block.get("signInPath")
    if sign_in_path == "captured":
        raise PilotContractError(
            REFUSAL_SIGN_IN_PATH_RETIRED_CAPTURED,
            "pilot.signInPath",
        )
    if sign_in_path not in SIGN_IN_PATHS:
        raise PilotContractError(REFUSAL_SIGN_IN_PATH_INVALID, "pilot.signInPath")
    return sign_in_path


def _validate_credential_set(block):
    credential_set = block.get("credentialSet")
    if not _is_json_array(credential_set) or not credential_set:
        raise PilotContractError(REFUSAL_CREDENTIAL_SET_EMPTY, "pilot.credentialSet")
    seen_accounts = set()
    for index, entry in enumerate(credential_set):
        path = "pilot.credentialSet[%d]" % index
        if not isinstance(entry, dict):
            raise PilotContractError(REFUSAL_CREDENTIAL_SET_INVALID, path)
        if "expectedIdentity" in entry:
            raise PilotContractError(
                REFUSAL_EXPECTED_IDENTITY_INLINE_REFUSED,
                path + ".expectedIdentity",
            )
        _check_unknown_keys(entry, _CREDENTIAL_ENTRY_KEYS, path)
        account = entry.get("account")
        if not isinstance(account, str) or not account:
            raise PilotContractError(REFUSAL_ACCOUNT_KEY_INVALID, path + ".account")
        if account in seen_accounts:
            raise PilotContractError(REFUSAL_ACCOUNT_KEY_DUPLICATE, path + ".account")
        seen_accounts.add(account)
        role = entry.get("role")
        if not isinstance(role, str) or not role:
            raise PilotContractError(REFUSAL_ACCOUNT_ROLE_MISSING, path + ".role")


def _validate_capture_surface_and_options(block):
    capture_surface = block.get("captureSurface")
    if not _is_json_array(capture_surface) or not capture_surface:
        raise PilotContractError(REFUSAL_CAPTURE_SURFACE_INVALID, "pilot.captureSurface")
    try:
        required_options = pilot_seed.required_context_options(capture_surface)
    except pilot_seed.PilotSeedError as exc:
        reason = _SEED_SURFACE_REFUSALS.get(exc.reason, REFUSAL_CAPTURE_SURFACE_INVALID)
        raise PilotContractError(reason, "pilot.captureSurface") from exc
    capture_options = block.get("captureOptions")
    if not _is_valid_capture_options(capture_options):
        raise PilotContractError(REFUSAL_CAPTURE_OPTIONS_INVALID, "pilot.captureOptions")
    if capture_options != required_options:
        raise PilotContractError(REFUSAL_CAPTURE_OPTIONS_MISMATCH, "pilot.captureOptions")


def _validate_validity_provenance(block):
    provenance = block.get("validityProvenance")
    if provenance not in VALIDITY_PROVENANCE:
        raise PilotContractError(
            REFUSAL_VALIDITY_PROVENANCE_INVALID,
            "pilot.validityProvenance",
        )


def _validate_identity_probe(block):
    identity_probe = block.get("identityProbe")
    if not isinstance(identity_probe, dict):
        raise PilotContractError(REFUSAL_IDENTITY_PROBE_INVALID, "pilot.identityProbe")
    _check_unknown_keys(identity_probe, _IDENTITY_PROBE_KEYS, "pilot.identityProbe")
    path_value = identity_probe.get("path")
    if not isinstance(path_value, str) or not path_value:
        raise PilotContractError(REFUSAL_IDENTITY_PROBE_INVALID, "pilot.identityProbe.path")
    expectation = identity_probe.get("unseededExpectation")
    if expectation not in pilot_probe.ALL_PROBE_REASONS:
        raise PilotContractError(
            REFUSAL_IDENTITY_PROBE_EXPECTATION_UNKNOWN,
            "pilot.identityProbe.unseededExpectation",
        )


def _validate_cleanup(block):
    cleanup = block.get("cleanup")
    if not isinstance(cleanup, dict):
        raise PilotContractError(REFUSAL_CLEANUP_COMMAND_INVALID, "pilot.cleanup")
    _check_unknown_keys(cleanup, _CLEANUP_KEYS, "pilot.cleanup")
    command = cleanup.get("command")
    if not _is_command_argv(command):
        raise PilotContractError(REFUSAL_CLEANUP_COMMAND_INVALID, "pilot.cleanup.command")
    if not any(NAMESPACE_PLACEHOLDER in part for part in command):
        raise PilotContractError(REFUSAL_CLEANUP_UNPARAMETERIZED, "pilot.cleanup.command")
    if NAMESPACE_PLACEHOLDER in command[0]:
        raise PilotContractError(
            REFUSAL_CLEANUP_PLACEHOLDER_IN_ARGV0,
            "pilot.cleanup.command",
        )


def _validate_administrative_max(block):
    value = block.get("administrativeMax")
    if not _is_int(value) or value < 1:
        raise PilotContractError(REFUSAL_ADMINISTRATIVE_MAX_INVALID, "pilot.administrativeMax")


def _validate_effects_escape(block):
    if "effectsEscape" not in block:
        raise PilotContractError(REFUSAL_EFFECTS_ESCAPE_ABSENT, "pilot.effectsEscape")
    effects_escape = block["effectsEscape"]
    if not isinstance(effects_escape, dict):
        raise PilotContractError(REFUSAL_EFFECTS_ESCAPE_INVALID, "pilot.effectsEscape")
    _check_unknown_keys(effects_escape, _EFFECTS_ESCAPE_KEYS, "pilot.effectsEscape")
    can_escape = effects_escape.get("canEscape")
    if not _is_bool(can_escape):
        raise PilotContractError(
            REFUSAL_EFFECTS_ESCAPE_INVALID,
            "pilot.effectsEscape.canEscape",
        )
    evidence = effects_escape.get("evidence")
    if not isinstance(evidence, str) or not evidence:
        raise PilotContractError(
            REFUSAL_EFFECTS_ESCAPE_EVIDENCE_MISSING,
            "pilot.effectsEscape.evidence",
        )


def _validate_policy_ref(block):
    policy_ref = block.get("policyRef")
    if not isinstance(policy_ref, dict):
        raise PilotContractError(REFUSAL_POLICY_REF_MISSING, "pilot.policyRef")
    _check_unknown_keys(policy_ref, _POLICY_REF_KEYS, "pilot.policyRef")
    declaration = policy_ref.get("declaration")
    if not isinstance(declaration, str) or not declaration:
        raise PilotContractError(REFUSAL_POLICY_REF_MISSING, "pilot.policyRef.declaration")


def _validate_attended(block, sign_in_path):
    attended = block.get("attended")
    if _required_block_key(sign_in_path) == "attended":
        if attended is None:
            raise PilotContractError(
                REFUSAL_ATTENDED_DECLARATION_MISSING,
                "pilot.attended",
            )
    if attended is None:
        return
    if not isinstance(attended, dict):
        raise PilotContractError(
            REFUSAL_ATTENDED_DECLARATION_INVALID,
            "pilot.attended",
        )
    _check_unknown_keys(attended, _ATTENDED_KEYS, "pilot.attended")
    vehicle = attended.get("vehicle")
    if not isinstance(vehicle, str) or not vehicle or vehicle not in ATTENDED_VEHICLES:
        raise PilotContractError(
            REFUSAL_ATTENDED_VEHICLE_INVALID,
            "pilot.attended.vehicle",
        )


def _validate_mint(block, sign_in_path):
    mint = block.get("mint")
    if _required_block_key(sign_in_path) == "mint":
        if mint is None:
            raise PilotContractError(REFUSAL_MINT_DECLARATION_MISSING, "pilot.mint")
    if mint is None:
        return
    if not isinstance(mint, dict):
        raise PilotContractError(REFUSAL_MINT_ENVELOPE_INCOMPLETE, "pilot.mint")
    if "mintableAccounts" in mint:
        raise PilotContractError(
            REFUSAL_MINTABLE_ALLOWLIST_INLINE_REFUSED,
            "pilot.mint.mintableAccounts",
        )
    _check_unknown_keys(mint, _MINT_KEYS, "pilot.mint")
    envelope = mint.get("envelope")
    if not isinstance(envelope, dict):
        raise PilotContractError(REFUSAL_MINT_ENVELOPE_INCOMPLETE, "pilot.mint.envelope")
    _check_unknown_keys(envelope, _MINT_ENVELOPE_KEYS, "pilot.mint.envelope")
    flag_var = envelope.get("enablingFlagEnvVar")
    if not isinstance(flag_var, str) or not flag_var:
        raise PilotContractError(
            REFUSAL_MINT_ENVELOPE_INCOMPLETE,
            "pilot.mint.envelope.enablingFlagEnvVar",
        )
    enabled_scopes = envelope.get("enabledScopes")
    forbidden_scopes = envelope.get("forbiddenScopes")
    if not _is_json_array(enabled_scopes):
        raise PilotContractError(
            REFUSAL_MINT_ENVELOPE_INCOMPLETE,
            "pilot.mint.envelope.enabledScopes",
        )
    if not _is_json_array(forbidden_scopes):
        raise PilotContractError(
            REFUSAL_MINT_ENVELOPE_INCOMPLETE,
            "pilot.mint.envelope.forbiddenScopes",
        )
    for index, scope in enumerate(enabled_scopes):
        if not isinstance(scope, str):
            raise PilotContractError(
                REFUSAL_MINT_ENVELOPE_INCOMPLETE,
                "pilot.mint.envelope.enabledScopes[%d]" % index,
            )
    for index, scope in enumerate(forbidden_scopes):
        if not isinstance(scope, str):
            raise PilotContractError(
                REFUSAL_MINT_ENVELOPE_INCOMPLETE,
                "pilot.mint.envelope.forbiddenScopes[%d]" % index,
            )
    enabled_set = set(enabled_scopes)
    forbidden_set = set(forbidden_scopes)
    if enabled_set & forbidden_set:
        raise PilotContractError(
            REFUSAL_MINT_ENVELOPE_SCOPE_CONFLICT,
            "pilot.mint.envelope",
        )
    gate_off = envelope.get("gateOffTestCommand")
    if not _is_command_argv(gate_off):
        raise PilotContractError(
            REFUSAL_MINT_GATE_OFF_TEST_MISSING,
            "pilot.mint.envelope.gateOffTestCommand",
        )
    sentinel = mint.get("sentinelIdentifier")
    if not isinstance(sentinel, str) or not sentinel:
        raise PilotContractError(REFUSAL_MINT_SENTINEL_MISSING, "pilot.mint.sentinelIdentifier")


def _check_unknown_keys(obj, allowed, path):
    unknown = set(obj.keys()) - allowed
    if unknown:
        key = sorted(unknown)[0]
        raise PilotContractError(REFUSAL_UNKNOWN_FIELD, "%s.%s" % (path, key))


def _is_valid_capture_options(capture_options):
    if not isinstance(capture_options, dict):
        return False
    if set(capture_options.keys()) != _CAPTURE_OPTION_KEYS:
        return False
    return _is_bool(capture_options["indexedDB"]) and _is_bool(capture_options["credentials"])


def _is_command_argv(command):
    if not _is_json_array(command) or not command:
        return False
    return all(isinstance(part, str) and part for part in command)


def _is_json_array(value):
    return isinstance(value, list)


def _is_bool(value):
    return type(value) is bool


def _is_int(value):
    return type(value) is int


_verify_sign_in_path_required_block_complete()


def _nfc_normalize(value):
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, dict):
        return {_nfc_normalize(k): _nfc_normalize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_nfc_normalize(item) for item in value]
    return value
