"""App-lifecycle exercise harness for attended-seeding navigation traces (B4).

Grades an observed navigation trace against a slot's declared origin and permitted
redirect allowlist so an app-lifecycle declaration can be exercised before stand-up.

Non-goals: no browser driving and no network I/O — this module is pure grading of a
navigation trace the caller observed; attended seeding orchestration is B4's sibling.
"""
import json
from urllib.parse import urlsplit

import pilot_contract
import pilot_slot

REFUSAL_DECLARATION_SLOT_INVALID = "lifecycle-exercise-declaration-slot-invalid"
REFUSAL_DECLARATION_INVALID = "lifecycle-exercise-declaration-invalid"
REFUSAL_ORIGIN_INVALID = "lifecycle-exercise-origin-invalid"
REFUSAL_REDIRECT_INVALID = "lifecycle-exercise-redirect-invalid"
REFUSAL_TRACE_INVALID = "lifecycle-exercise-trace-invalid"
REFUSAL_TRACE_EMPTY = "lifecycle-exercise-trace-empty"
REFUSAL_NAVIGATION_ESCAPED = "lifecycle-exercise-navigation-escaped"
REFUSAL_TRACE_DID_NOT_RETURN = "lifecycle-exercise-trace-did-not-return"
REFUSAL_RECEIPT_ARGUMENT_INVALID = "lifecycle-exercise-receipt-argument-invalid"

EVIDENCE_REFUSAL_UNPINNED = "lifecycle-exercise-refused"

_REFUSAL_TOKENS = frozenset({
    REFUSAL_DECLARATION_SLOT_INVALID,
    REFUSAL_DECLARATION_INVALID,
    REFUSAL_ORIGIN_INVALID,
    REFUSAL_REDIRECT_INVALID,
    REFUSAL_TRACE_INVALID,
    REFUSAL_TRACE_EMPTY,
    REFUSAL_NAVIGATION_ESCAPED,
    REFUSAL_TRACE_DID_NOT_RETURN,
    REFUSAL_RECEIPT_ARGUMENT_INVALID,
})


class PilotLifecycleExerciseError(Exception):
    """App-lifecycle exercise refusal."""

    def __init__(self, reason, detail=None):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


def _json_serializable(value):
    try:
        json.dumps(value, ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError):
        return False
    return True


def _origin_host_part(host):
    host_lower = host.lower()
    if ":" in host_lower:
        return "[%s]" % host_lower
    return host_lower


def normalize_origin(value):
    """Return canonical ``scheme://host[:port]`` for a URL or origin string.

    Malformed authorities refuse with ``lifecycle-exercise-origin-invalid`` instead of
    letting a bare ``ValueError`` escape from ``urlsplit`` or port parsing.
    """
    # bite-axis: origin canonicalization — only http(s) with valid host; default ports stripped;
    # never compare origins by string prefix.
    if not isinstance(value, str) or not value:
        raise PilotLifecycleExerciseError(REFUSAL_ORIGIN_INVALID)
    if any(ch.isspace() or ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise PilotLifecycleExerciseError(REFUSAL_ORIGIN_INVALID)

    try:
        parsed = urlsplit(value)
    except ValueError:
        raise PilotLifecycleExerciseError(REFUSAL_ORIGIN_INVALID)
    scheme = parsed.scheme.lower() if parsed.scheme else ""
    if scheme not in ("http", "https"):
        raise PilotLifecycleExerciseError(REFUSAL_ORIGIN_INVALID)
    if parsed.username is not None or parsed.password is not None:
        raise PilotLifecycleExerciseError(REFUSAL_ORIGIN_INVALID)

    host = parsed.hostname
    if not host:
        raise PilotLifecycleExerciseError(REFUSAL_ORIGIN_INVALID)

    try:
        port = parsed.port
    except ValueError:
        raise PilotLifecycleExerciseError(REFUSAL_ORIGIN_INVALID)
    host_part = _origin_host_part(host)
    default_port = 80 if scheme == "http" else 443
    if port is None or port == default_port:
        return "%s://%s" % (scheme, host_part)
    return "%s://%s:%d" % (scheme, host_part, port)


def _normalize_redirect_list(permitted_redirects):
    if not isinstance(permitted_redirects, list):
        raise PilotLifecycleExerciseError(REFUSAL_REDIRECT_INVALID)
    seen = set()
    normalized = []
    for redirect in permitted_redirects:
        try:
            parsed = normalize_origin(redirect)
        except PilotLifecycleExerciseError:
            raise PilotLifecycleExerciseError(REFUSAL_REDIRECT_INVALID)
        if parsed not in seen:
            seen.add(parsed)
            normalized.append(parsed)
    return sorted(normalized)


def _allowed_origins(origin, permitted_redirects):
    allowed = {origin}
    allowed.update(permitted_redirects)
    return allowed


def evaluate_trace(trace, *, origin, permitted_redirects):
    """Grade an observed navigation trace against the declaration."""
    # bite-axis: trace grading — every origin must be allowed; trace must start and end at the
    # declared origin; prefix-lookalike hosts refuse via exact normalized comparison.
    if not isinstance(trace, list):
        return {
            "ok": False,
            "reason": REFUSAL_TRACE_INVALID,
            "origins": [],
            "escaped": None,
        }
    if not trace:
        return {
            "ok": False,
            "reason": REFUSAL_TRACE_EMPTY,
            "origins": [],
            "escaped": None,
        }

    try:
        declared_origin = normalize_origin(origin)
    except PilotLifecycleExerciseError:
        return {
            "ok": False,
            "reason": REFUSAL_ORIGIN_INVALID,
            "origins": [],
            "escaped": None,
        }

    try:
        normalized_redirects = _normalize_redirect_list(permitted_redirects)
    except PilotLifecycleExerciseError:
        return {
            "ok": False,
            "reason": REFUSAL_REDIRECT_INVALID,
            "origins": [],
            "escaped": None,
        }

    allowed = _allowed_origins(declared_origin, normalized_redirects)
    origins = []
    for index, url in enumerate(trace):
        if not isinstance(url, str):
            return {
                "ok": False,
                "reason": REFUSAL_TRACE_INVALID,
                "origins": origins,
                "escaped": None,
            }
        try:
            normalized = normalize_origin(url)
        except PilotLifecycleExerciseError:
            return {
                "ok": False,
                "reason": REFUSAL_TRACE_INVALID,
                "origins": origins,
                "escaped": None,
            }
        origins.append(normalized)
        if normalized not in allowed:
            return {
                "ok": False,
                "reason": REFUSAL_NAVIGATION_ESCAPED,
                "origins": origins,
                "escaped": {"origin": normalized, "index": index},
            }

    if origins[0] != declared_origin or origins[-1] != declared_origin:
        return {
            "ok": False,
            "reason": REFUSAL_TRACE_DID_NOT_RETURN,
            "origins": origins,
            "escaped": None,
        }

    return {
        "ok": True,
        "reason": None,
        "origins": origins,
        "escaped": None,
    }


def _gate_declaration(declaration):
    if not isinstance(declaration, dict):
        raise PilotLifecycleExerciseError(REFUSAL_RECEIPT_ARGUMENT_INVALID)
    inner = declaration.get("declaration")
    if not isinstance(inner, dict):
        raise PilotLifecycleExerciseError(REFUSAL_RECEIPT_ARGUMENT_INVALID)
    return inner


def app_lifecycle_declaration(*, slot_ref, policy_digest, origin, permitted_redirects):
    """Return the digested declaration plus slot, generation, and policyDigest metadata.

    Only the raw-policy ``declaration`` member is digested; redirect order is significant.
    """
    # bite-axis: declaration binding — slot ref and policy digest as metadata; the digested
    # declaration matches pilot_provision's raw policy origin and permittedRedirects.
    try:
        slot, generation = pilot_slot.parse_slot_ref(slot_ref)
    except pilot_slot.PilotSlotError:
        raise PilotLifecycleExerciseError(REFUSAL_DECLARATION_SLOT_INVALID)

    if not isinstance(policy_digest, str) or not policy_digest:
        raise PilotLifecycleExerciseError(REFUSAL_DECLARATION_INVALID)

    try:
        normalize_origin(origin)
    except PilotLifecycleExerciseError:
        raise

    try:
        _normalize_redirect_list(permitted_redirects)
    except PilotLifecycleExerciseError:
        raise

    return {
        "declaration": {
            "origin": origin,
            "permittedRedirects": permitted_redirects,
        },
        "slot": slot,
        "generation": generation,
        "policyDigest": policy_digest,
    }


def _validate_evaluate_trace_result(result, declaration):
    """Require result to be a real evaluate_trace return shape bound to declaration."""
    gate_decl = _gate_declaration(declaration)
    declared_origin = gate_decl.get("origin")
    declared_redirects = gate_decl.get("permittedRedirects")
    if not isinstance(declared_origin, str) or not isinstance(declared_redirects, list):
        raise PilotLifecycleExerciseError(REFUSAL_RECEIPT_ARGUMENT_INVALID)

    if not isinstance(result, dict):
        raise PilotLifecycleExerciseError(REFUSAL_RECEIPT_ARGUMENT_INVALID)

    ok = result.get("ok")
    if type(ok) is not bool:
        raise PilotLifecycleExerciseError(REFUSAL_RECEIPT_ARGUMENT_INVALID)

    reason = result.get("reason")
    if ok is True:
        if reason is not None:
            raise PilotLifecycleExerciseError(REFUSAL_RECEIPT_ARGUMENT_INVALID)
    elif not isinstance(reason, str) or not reason:
        raise PilotLifecycleExerciseError(REFUSAL_RECEIPT_ARGUMENT_INVALID)

    origins = result.get("origins")
    if not isinstance(origins, list):
        raise PilotLifecycleExerciseError(REFUSAL_RECEIPT_ARGUMENT_INVALID)

    escaped = result.get("escaped")
    if ok is True:
        if escaped is not None:
            raise PilotLifecycleExerciseError(REFUSAL_RECEIPT_ARGUMENT_INVALID)
    elif escaped is not None and not isinstance(escaped, dict):
        raise PilotLifecycleExerciseError(REFUSAL_RECEIPT_ARGUMENT_INVALID)

    for trace_origin in origins:
        if not isinstance(trace_origin, str):
            raise PilotLifecycleExerciseError(REFUSAL_RECEIPT_ARGUMENT_INVALID)

    if ok is True:
        try:
            normalized_origin = normalize_origin(declared_origin)
            normalized_redirects = _normalize_redirect_list(declared_redirects)
        except PilotLifecycleExerciseError:
            raise PilotLifecycleExerciseError(REFUSAL_RECEIPT_ARGUMENT_INVALID)
        allowed = _allowed_origins(normalized_origin, normalized_redirects)
        for trace_origin in origins:
            if trace_origin not in allowed:
                raise PilotLifecycleExerciseError(REFUSAL_RECEIPT_ARGUMENT_INVALID)
        if (
            not origins
            or origins[0] != normalized_origin
            or origins[-1] != normalized_origin
        ):
            raise PilotLifecycleExerciseError(REFUSAL_RECEIPT_ARGUMENT_INVALID)

    return ok, origins, reason


def app_lifecycle_receipt(declaration, result, *, exercised_at):
    """Build the registry record for kind app-lifecycle."""
    # bite-axis: receipt assembly — pass/fail from evaluate_trace; evidence never carries full
    # URLs; kind must remain in DECLARATION_KINDS; result must bind to declaration.
    if "app-lifecycle" not in pilot_contract.DECLARATION_KINDS:
        raise PilotLifecycleExerciseError(REFUSAL_RECEIPT_ARGUMENT_INVALID)

    if not isinstance(exercised_at, str) or not exercised_at:
        raise PilotLifecycleExerciseError(REFUSAL_RECEIPT_ARGUMENT_INVALID)

    if not isinstance(declaration, dict) or not _json_serializable(declaration):
        raise PilotLifecycleExerciseError(REFUSAL_RECEIPT_ARGUMENT_INVALID)

    ok, origins, reason = _validate_evaluate_trace_result(result, declaration)

    if ok is True:
        evidence = "%d origin(s) visited" % len(origins)
        receipt_result = "pass"
    else:
        evidence = reason if reason in _REFUSAL_TOKENS else EVIDENCE_REFUSAL_UNPINNED
        receipt_result = "fail"

    return {
        "kind": "app-lifecycle",
        "declarationDigest": pilot_contract.declaration_digest(_gate_declaration(declaration)),
        "exercisedAt": exercised_at,
        "receipt": {
            "result": receipt_result,
            "evidence": evidence,
        },
    }


def require_app_lifecycle_exercised(registry, declaration):
    """Require a matching exercised app-lifecycle record in the registry.

    A registry record is the durable receipt of an exercise that happened; it is never a
    substitute for the live navigation check in the current preflight. ``is_exercised`` carries
    no freshness or launched-instance binding — the declaration binds slot, generation, and
    policy digest.
    """
    return pilot_contract.require_exercised(
        registry, "app-lifecycle", _gate_declaration(declaration),
    )
