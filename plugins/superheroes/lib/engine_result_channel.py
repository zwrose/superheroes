"""Declared result channel: one schema home per (engine, run-kind) shape (#1270 WO-A).

Pure + deterministic. Stdlib-only; never imports jsonschema at runtime.
"""
from __future__ import annotations

import model_registry
import payload_contracts
import review_findings_schema

CHANNEL_NATIVE = "native"
CHANNEL_MARKER = "marker"

RUN_KIND_REVIEW = "review"
RUN_KIND_WRITE = "write"

# Align with engine_dispatch.MAX_STDOUT_CAPTURE (8 MiB): native results are structured JSON
# written to a dedicated file; the same ceiling bounds runaway payloads without a second literal.
NATIVE_RESULT_MAX_BYTES = 8 * 1024 * 1024

# Write tail signals graded by engine_adapter._grade_build_report_obj (CONVENTIONS §11).
WRITE_SIGNAL_ENUM = ("ok", "plan_wrong", "needs_context")

REVIEW_RESULT_KINDS = ("findings", "verdicts", "grouping", "ruling")

_PAYLOAD_CONTAINER_KEYS = ("findings", "verdicts", "grouping")

_RULING_BRANCH_FIELDS = ("id", "ruling", "reason", "newIssues", "evidence", "auditorVendor")

_CHANNEL_BY_ENGINE = {
    "codex": CHANNEL_NATIVE,
    "cursor": CHANNEL_MARKER,
    "claude": CHANNEL_MARKER,
}

_ALLOWED_SCHEMA_KEYWORDS = frozenset({
    "type",
    "required",
    "properties",
    "additionalProperties",
    "enum",
    "items",
    "anyOf",
})


class UnknownEngineError(ValueError):
    """Raised when channel_for receives an engine outside the closed registry set."""


def channel_for(engine):
    """Return the declared result channel for a registered dispatch engine."""
    if not isinstance(engine, str) or engine not in _CHANNEL_BY_ENGINE:
        raise UnknownEngineError(
            "unknown engine %r; registered engines: %s"
            % (engine, ", ".join(model_registry.vendors()))
        )
    return _CHANNEL_BY_ENGINE[engine]


def declared_schema(engine, run_kind, expected_result_kind=None):
    """Return the JSON Schema dict for this (engine, run-kind), or None on marker channel."""
    if channel_for(engine) == CHANNEL_MARKER:
        return None
    if run_kind == RUN_KIND_REVIEW:
        return _review_root_schema(expected_result_kind)
    if run_kind == RUN_KIND_WRITE:
        return _write_root_schema()
    raise ValueError(
        "unknown run_kind %r; expected %r or %r"
        % (run_kind, RUN_KIND_REVIEW, RUN_KIND_WRITE)
    )


def validate(schema, value):
    """Validate value against schema. Returns (ok, reason). Never raises."""
    if schema is None:
        return True, ""
    try:
        _validate(schema, value, "$")
        return True, ""
    except _ValidationError as exc:
        return False, str(exc)


def _sanitize_schema_node(node):
    """Keep only keywords our validator implements (drops description, etc.)."""
    if not isinstance(node, dict):
        return node
    out = {}
    for key, value in node.items():
        if key not in _ALLOWED_SCHEMA_KEYWORDS:
            continue
        if key in ("properties",):
            out[key] = {
                name: _sanitize_schema_node(sub)
                for name, sub in value.items()
            }
        elif key == "items":
            out[key] = _sanitize_schema_node(value)
        elif key == "anyOf":
            out[key] = [_sanitize_schema_node(sub) for sub in value]
        else:
            out[key] = value
    return out


def _nullable_type_schema(prop):
    """Express an optional binding as required-and-nullable in strict mode."""
    if not isinstance(prop, dict):
        return prop
    if "enum" in prop:
        enums = list(prop["enum"])
        if None not in enums:
            enums.append(None)
        out = dict(prop)
        out["enum"] = enums
        return out
    type_spec = prop.get("type")
    if type_spec is None:
        return prop
    if isinstance(type_spec, list):
        if "null" in type_spec:
            return prop
        out = dict(prop)
        out["type"] = list(type_spec) + ["null"]
        return out
    out = dict(prop)
    out["type"] = [type_spec, "null"]
    return out


def _json_schema_for_type_token(token):
    if token not in payload_contracts.TYPE_TOKENS:
        raise ValueError("unknown type token %r" % (token,))
    if token == "string":
        return {"type": "string"}
    if token == "non-empty-string":
        # non-empty-string maps to string here; non-emptiness is enforced by
        # payload_contracts' own checks, not by this schema.
        return {"type": "string"}
    if token == "boolean":
        return {"type": "boolean"}
    if token == "integer":
        return {"type": "integer"}
    if token == "list":
        return {"type": "array"}
    if token == "object":
        return {"type": "object"}
    if token == "absolute-path":
        return {"type": "string"}
    if token == "any":
        return {}
    if token == "list-of-objects":
        return {"type": "array", "items": {"type": "object"}}
    if token == "nullable-list-of-objects":
        return {"type": ["array", "null"], "items": {"type": "object"}}
    raise ValueError("unhandled type token %r" % (token,))


def _element_object_schema(elem_contract):
    required = list(elem_contract.get("required") or [])
    optional = list(elem_contract.get("optional") or [])
    types = elem_contract.get("types") or {}
    enums = elem_contract.get("enums") or {}
    all_fields = required + optional
    properties = {}
    for field in all_fields:
        prop = dict(_json_schema_for_type_token(types.get(field, "any")))
        if field in enums:
            prop["enum"] = list(enums[field])
        if field in optional:
            prop = _nullable_type_schema(prop)
        properties[field] = prop
    return {
        "type": "object",
        "additionalProperties": False,
        "required": all_fields,
        "properties": properties,
    }


def _top_level_field_schema(contract, field, *, optional_fields=()):
    types = contract.get("types") or {}
    elements = contract.get("elements") or {}
    enums = contract.get("enums") or {}
    tok = types.get(field, "any")
    if tok == "list-of-objects":
        elem = elements.get(field) or {}
        schema = {
            "type": "array",
            "items": _element_object_schema(elem),
        }
    elif tok == "nullable-list-of-objects":
        elem = elements.get(field) or {}
        schema = {
            "type": ["array", "null"],
            "items": _element_object_schema(elem),
        }
    else:
        schema = _json_schema_for_type_token(tok)
        if field in enums:
            schema = dict(schema)
            schema["enum"] = list(enums[field])
    if field in optional_fields:
        schema = _nullable_type_schema(schema)
    return schema


def _finding_member_schema():
    properties = {}
    for key in review_findings_schema.CANONICAL_MEMBER_KEYS:
        raw = review_findings_schema.FINDING_PROPERTY_SCHEMAS[key]
        properties[key] = _sanitize_schema_node(dict(raw))
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(review_findings_schema.CANONICAL_MEMBER_KEYS),
        "properties": properties,
    }


def _null_property():
    return {"type": "null"}


def _investigated_schema():
    return {"type": ["array", "null"], "items": {"type": "string"}}


def _phase_contract(phase):
    contract, reason = payload_contracts.payload_contract(phase)
    if reason is not None:
        raise ValueError("payload contract unavailable for phase %r: %s" % (phase, reason))
    return contract


def _branch_payload_schema(kind):
    if kind == "findings":
        return {
            "type": "array",
            "items": _finding_member_schema(),
        }
    if kind == "verdicts":
        contract = _phase_contract(payload_contracts.P_VERIFIERS)
        return _top_level_field_schema(contract, "verdicts")
    if kind == "grouping":
        contract = _phase_contract(payload_contracts.P_SYNTHESIS)
        return _top_level_field_schema(contract, "grouping")
    if kind == "ruling":
        contract = _phase_contract(payload_contracts.P_AUDITS)
        ordered = list(contract.get("required") or []) + list(contract.get("optional") or ())
        optional = set(contract.get("optional") or ())
        properties = {}
        for field in ordered:
            properties[field] = _top_level_field_schema(
                contract, field, optional_fields=optional)
        return {
            "type": "object",
            "additionalProperties": False,
            "required": ordered,
            "properties": properties,
        }
    raise ValueError("unknown review result kind %r" % (kind,))


def _review_branch_schema(kind):
    payload_schema = _branch_payload_schema(kind)
    properties = {
        "resultKind": {"type": "string", "enum": [kind]},
        "investigated": _investigated_schema(),
    }
    required = ["resultKind", "investigated"]
    for key in _PAYLOAD_CONTAINER_KEYS:
        if kind != "ruling" and key == kind:
            properties[key] = payload_schema
        else:
            properties[key] = _null_property()
        required.append(key)
    if kind == "ruling":
        ruling_props = payload_schema["properties"]
        for field in _RULING_BRANCH_FIELDS:
            properties[field] = ruling_props[field]
            required.append(field)
    else:
        for field in _RULING_BRANCH_FIELDS:
            properties[field] = _null_property()
            required.append(field)
    return {
        "type": "object",
        "additionalProperties": False,
        "required": required,
        "properties": properties,
    }


def _review_root_schema(expected_result_kind):
    kinds = REVIEW_RESULT_KINDS
    if expected_result_kind is not None:
        if expected_result_kind not in REVIEW_RESULT_KINDS:
            raise ValueError("unknown expected_result_kind %r" % (expected_result_kind,))
        kinds = (expected_result_kind,)
    branches = [_review_branch_schema(kind) for kind in kinds]
    result_schema = branches[0] if len(branches) == 1 else {"anyOf": branches}
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["result"],
        "properties": {
            "result": result_schema,
        },
    }


def _write_root_schema():
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["ok", "signal", "report", "evidence"],
        "properties": {
            "ok": {"type": "boolean"},
            "signal": {"type": "string", "enum": list(WRITE_SIGNAL_ENUM)},
            "report": {"type": "string"},
            "evidence": {
                "type": "object",
                "additionalProperties": False,
                "required": ["testFailed", "testPassed"],
                "properties": {
                    "testFailed": {"type": "boolean"},
                    "testPassed": {"type": "boolean"},
                },
            },
        },
    }


class _ValidationError(Exception):
    pass


def _type_matches(type_spec, value):
    if isinstance(type_spec, list):
        return any(_type_matches(one, value) for one in type_spec)
    if type_spec == "string":
        return isinstance(value, str)
    if type_spec == "boolean":
        return isinstance(value, bool)
    if type_spec == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if type_spec == "null":
        return value is None
    if type_spec == "array":
        return isinstance(value, list)
    if type_spec == "object":
        return isinstance(value, dict)
    raise _ValidationError("unknown type specifier %r" % (type_spec,))


def _validate(schema, value, path):
    if not isinstance(schema, dict):
        raise _ValidationError("%s: schema must be an object" % path)
    unknown = set(schema) - _ALLOWED_SCHEMA_KEYWORDS
    if unknown:
        raise _ValidationError(
            "%s: unknown schema keyword(s): %s"
            % (path, ", ".join(sorted(unknown)))
        )

    if "anyOf" in schema:
        failures = []
        for index, branch in enumerate(schema["anyOf"]):
            try:
                _validate(branch, value, "%s.anyOf[%d]" % (path, index))
                return
            except _ValidationError as exc:
                failures.append(str(exc))
        raise _ValidationError(
            "%s: anyOf failed (%d branches): %s"
            % (path, len(failures), "; ".join(failures))
        )

    if "type" in schema and not _type_matches(schema["type"], value):
        raise _ValidationError(
            "%s: expected type %r, got %s"
            % (path, schema["type"], type(value).__name__)
        )

    if "enum" in schema and value not in schema["enum"]:
        raise _ValidationError(
            "%s: value %r not in enum %r" % (path, value, schema["enum"])
        )

    if isinstance(value, dict):
        if schema.get("additionalProperties") is False:
            allowed = set((schema.get("properties") or {}).keys())
            extra = set(value) - allowed
            if extra:
                raise _ValidationError(
                    "%s: additional properties forbidden: %s"
                    % (path, ", ".join(sorted(extra)))
                )
        for req in schema.get("required") or []:
            if req not in value:
                raise _ValidationError("%s: missing required property %r" % (path, req))
        props = schema.get("properties") or {}
        for key, subschema in props.items():
            if key in value:
                _validate(subschema, value[key], "%s.%s" % (path, key))
    elif isinstance(value, list) and "items" in schema:
        item_schema = schema["items"]
        for index, item in enumerate(value):
            _validate(item_schema, item, "%s[%d]" % (path, index))
