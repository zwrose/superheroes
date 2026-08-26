"""Declared home for review findings-member schema (#949, #1145).

Canonical member keys, substance/structural synonym census, engagement predicate,
normalizer, and rendered example object — single source; consumers import, never restate.
"""
import json
import os

import audits
import round_phases

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
REVIEW_FINDINGS_SCHEMA_REL = os.path.join("schemas", "review-findings.schema.json")
REVIEW_FINDINGS_SCHEMA_PATH = os.path.join(_LIB_DIR, REVIEW_FINDINGS_SCHEMA_REL)

# Fallback literals when the shipped schema cannot be read — must stay aligned with
# schemas/review-findings.schema.json; SCHEMA_READ_USED_FALLBACK exposes drift.
_FALLBACK_CANONICAL_MEMBER_KEYS = (
    "id",
    "severity",
    "dimension",
    "taxonomy",
    "title",
    "file",
    "line",
    "body",
    "suggestion",
    "evidence",
    "confidence",
    "tradeoff",
)
_FALLBACK_SEVERITY_TIERS = frozenset({"Critical", "Important", "Minor", "Nit"})
_FALLBACK_DIMENSION_ENUM = (
    "Architecture",
    "Code",
    "Security",
    "Test",
    "Failure-Mode",
    "Clarity",
    "Verifiability",
    "Coherence",
    "Safety-access",
    "Grounding",
)
_FALLBACK_CONFIDENCE_ENUM = ("High", "Low", None)
_FALLBACK_FINDING_PROPERTY_SCHEMAS = {
    key: {} for key in _FALLBACK_CANONICAL_MEMBER_KEYS
}
_FALLBACK_FINDING_PROPERTY_SCHEMAS["severity"] = {"enum": list(_FALLBACK_SEVERITY_TIERS)}
_FALLBACK_FINDING_PROPERTY_SCHEMAS["dimension"] = {"enum": list(_FALLBACK_DIMENSION_ENUM)}
_FALLBACK_FINDING_PROPERTY_SCHEMAS["confidence"] = {"enum": list(_FALLBACK_CONFIDENCE_ENUM)}
_FALLBACK_FINDING_PROPERTY_SCHEMAS["line"] = {"type": ["integer", "null"]}
_FALLBACK_FINDING_PROPERTY_SCHEMAS["tradeoff"] = {"type": ["boolean", "null"]}

SUBSTANCE_KEYS_CANONICAL = frozenset({"title", "body", "evidence", "suggestion"})

# Synonym key → canonical member key. Structural mappings are listed separately.
SUBSTANCE_KEY_SYNONYMS = {
    # already tolerated today (engine_adapter.py legacy census)
    "summary": "title",
    "message": "body",
    "description": "body",
    # PR #1143 brief-check (severity/part/defect/change)
    "defect": "body",
    "change": "suggestion",
    "reason": "evidence",  # verifier verdicts members (id/ruling/reason)
    "rationale": "evidence",  # synthesis grouping members
}

STRUCTURAL_KEY_SYNONYMS = {
    # PR #1143 brief-check — locator, not substance
    "part": "file",
}

SUBSTANCE_KEYS_LEGACY = frozenset({"summary", "message", "description"})
SUBSTANCE_KEYS_CENSUSED = frozenset({"defect", "change", "reason", "rationale"})

# Bracketed token unlikely in real review prose — closes near-copy bypass (#1145 brief check).
EXAMPLE_SENTINEL = "[RFS-EXAMPLE-SENTINEL-1145]"

CANONICAL_MEMBER_KEYS = ()
SEVERITY_TIERS = frozenset()
FINDING_PROPERTY_SCHEMAS = {}
SCHEMA_READ_USED_FALLBACK = False

_VERDICT_ENUM = frozenset(round_phases.VERDICTS)
_RULING_ENUM = frozenset(audits.AUDIT_RULINGS)


def review_findings_schema_path():
    """Return the absolute path to the shipped canonical review-findings schema."""
    return REVIEW_FINDINGS_SCHEMA_PATH


def _init_schema_constants():
    """Read canonical keys and severity tiers from the shipped schema once."""
    global CANONICAL_MEMBER_KEYS, SEVERITY_TIERS, FINDING_PROPERTY_SCHEMAS, SCHEMA_READ_USED_FALLBACK
    try:
        with open(REVIEW_FINDINGS_SCHEMA_PATH, encoding="utf-8") as fh:
            schema = json.load(fh)
        finding_props = schema["properties"]["findings"]["items"]["properties"]
        CANONICAL_MEMBER_KEYS = tuple(finding_props.keys())
        severity_enum = finding_props["severity"]["enum"]
        SEVERITY_TIERS = frozenset(severity_enum)
        FINDING_PROPERTY_SCHEMAS = finding_props
        SCHEMA_READ_USED_FALLBACK = False
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        CANONICAL_MEMBER_KEYS = _FALLBACK_CANONICAL_MEMBER_KEYS
        SEVERITY_TIERS = _FALLBACK_SEVERITY_TIERS
        FINDING_PROPERTY_SCHEMAS = _FALLBACK_FINDING_PROPERTY_SCHEMAS
        SCHEMA_READ_USED_FALLBACK = True


def _non_trivial_string(value):
    return isinstance(value, str) and value.strip() != ""


def _all_synonym_maps():
    merged = dict(SUBSTANCE_KEY_SYNONYMS)
    merged.update(STRUCTURAL_KEY_SYNONYMS)
    return merged


def _placeholder_field_value_count(value, placeholders):
    """Count string values that exactly equal an example placeholder (stripped)."""
    count = 0
    if isinstance(value, dict):
        for item in value.values():
            count += _placeholder_field_value_count(item, placeholders)
    elif isinstance(value, list):
        for item in value:
            count += _placeholder_field_value_count(item, placeholders)
    elif isinstance(value, str) and value.strip() in placeholders:
        count += 1
    return count


def _member_has_non_placeholder_substance(value, placeholders):
    """True when value carries non-empty content beyond exact placeholder strings."""
    if isinstance(value, dict):
        return any(
            _member_has_non_placeholder_substance(item, placeholders)
            for item in value.values()
        )
    if isinstance(value, list):
        return any(
            _member_has_non_placeholder_substance(item, placeholders)
            for item in value
        )
    if isinstance(value, str):
        stripped = value.strip()
        return stripped != "" and stripped not in placeholders
    return value is not None


_ECHO_SUBSTANCE_KEYS = (
    SUBSTANCE_KEYS_CANONICAL | SUBSTANCE_KEYS_LEGACY | SUBSTANCE_KEYS_CENSUSED
)


def _member_has_non_placeholder_substance_fields(member, placeholders):
    """True when substance (not structural) fields carry non-placeholder content."""
    if not isinstance(member, dict):
        return False
    for key in _ECHO_SUBSTANCE_KEYS:
        if key not in member:
            continue
        value = member[key]
        if isinstance(value, str):
            stripped = value.strip()
            if stripped != "" and stripped not in placeholders:
                return True
        elif value is not None and not isinstance(value, (dict, list)):
            return True
    return False


def member_carries_sentinel(member):
    # axis: placeholder field-value equality (not substring sentinel) refuses verbatim/near-copy echo
    """True when field values are example placeholders (verbatim/near-copy echo).

    Prose that merely embeds EXAMPLE_SENTINEL inside a real sentence is not an echo.
    """
    if not isinstance(member, dict):
        return False
    placeholders = example_member_values()
    placeholder_count = _placeholder_field_value_count(member, placeholders)
    if placeholder_count >= 2:
        return True
    if placeholder_count == 1 and not _member_has_non_placeholder_substance_fields(
        member, placeholders
    ):
        return True
    return False


def _member_has_censused_substance(member):
    for key in SUBSTANCE_KEYS_CENSUSED:
        if key in member and _non_trivial_string(member[key]):
            return True
    return False


def _member_has_id_enum_credential(member):
    """True when member carries non-empty id plus a schema-home verdict or ruling enum."""
    member_id = member.get("id")
    if not isinstance(member_id, str) or member_id.strip() == "":
        return False
    verdict = member.get("verdict")
    if isinstance(verdict, str) and verdict in _VERDICT_ENUM:
        return True
    ruling = member.get("ruling")
    if isinstance(ruling, str) and ruling in _RULING_ENUM:
        return True
    return False


def member_is_engaged(member):
    """True when a findings member carries substantive review content (not a hollow echo)."""
    if not isinstance(member, dict):
        return False

    for key in SUBSTANCE_KEYS_CANONICAL:
        if key in member and _non_trivial_string(member[key]):
            return True

    for key in SUBSTANCE_KEYS_LEGACY:
        if key in member and _non_trivial_string(member[key]):
            return True

    severity = member.get("severity")
    if isinstance(severity, str) and severity in SEVERITY_TIERS:
        if _member_has_censused_substance(member):
            return True

    if _member_has_id_enum_credential(member) and _member_has_censused_substance(member):
        return True

    return False


def normalize_member(member):
    """Return a new dict with canonical keys added for known synonyms; never mutates input."""
    if not isinstance(member, dict):
        return member
    out = dict(member)
    for synonym, canonical in _all_synonym_maps().items():
        if synonym in out and canonical not in out:
            out[canonical] = out[synonym]
    return out


def _placeholder_string(field_name):
    return "%s placeholder %s" % (field_name, EXAMPLE_SENTINEL)


def example_member_values():
    """Placeholder strings emitted by the example renderer (for verbatim-echo detection)."""
    values = set()
    for key in CANONICAL_MEMBER_KEYS:
        if key in ("line", "tradeoff"):
            continue
        values.add(_placeholder_string(key))
    values.add(_placeholder_string("investigated-path"))
    return frozenset(values)


def _shipped_finding_property_schemas():
    return FINDING_PROPERTY_SCHEMAS


def _first_schema_enum_member(field_schema):
    for member in field_schema.get("enum", ()):
        if member is not None:
            return member
    return None


def _example_value_for_field(key, field_schema):
    if key == "line":
        return None  # integer|null schema field — null placeholder
    if key == "tradeoff":
        return None  # boolean|null schema field — null placeholder
    if "enum" in field_schema:
        return _first_schema_enum_member(field_schema)
    return _placeholder_string(key)


def example_findings_object():
    """Format-only example object with exactly the canonical member keys."""
    field_schemas = _shipped_finding_property_schemas()
    member = {}
    for key in CANONICAL_MEMBER_KEYS:
        field_schema = field_schemas.get(key)
        if field_schema is None:
            if SCHEMA_READ_USED_FALLBACK:
                member[key] = _placeholder_string(key)
            else:
                member[key] = _example_value_for_field(key, field_schemas[key])
        else:
            member[key] = _example_value_for_field(key, field_schema)
    return {
        "findings": [member],
        "investigated": [_placeholder_string("investigated-path")],
    }


def example_prompt_block():
    """Rendered format-only prompt block wrapping the example JSON object."""
    payload = json.dumps(example_findings_object(), indent=2, sort_keys=True)
    return (
        "Format only — your findings replace every value; "
        "an echoed example grades hollow.\n"
        "%s" % payload
    )


_init_schema_constants()
