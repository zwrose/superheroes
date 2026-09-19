"""Declared result channel: one schema home per (engine, run-kind) shape (#1270 WO-A).

Pure + deterministic. Stdlib-only; never imports jsonschema at runtime.
Codex and cursor are both native-channel engines; result delivery differs by engine
(see ``_RESULT_DELIVERY_BY_ENGINE``).
"""
from __future__ import annotations

import engine_adapter
import model_registry
import payload_contracts
import review_findings_schema

CHANNEL_NATIVE = "native"
CHANNEL_MARKER = "marker"

RUN_KIND_REVIEW = "review"
RUN_KIND_WRITE = "write"

# Native results are structured JSON written to a dedicated file; the authoritative cap lives on
# engine_adapter.ENGINE_OUTPUT_MAX_BYTES (engine_dispatch.MAX_STDOUT_CAPTURE reads the same home).
NATIVE_RESULT_MAX_BYTES = engine_adapter.ENGINE_OUTPUT_MAX_BYTES

# Write tail signals graded by engine_adapter._grade_build_report_obj (CONVENTIONS §11).
WRITE_SIGNAL_ENUM = engine_adapter.WRITE_SIGNAL_ENUM

# Consumers import engine_adapter.REVIEW_RESULT_KINDS — never restate the tuple (CONVENTIONS §11).
REVIEW_RESULT_KINDS = engine_adapter.REVIEW_RESULT_KINDS

_PAYLOAD_CONTAINER_KEYS = ("findings", "verdicts", "grouping")

# Closed refinement table: fields whose payload_contracts token cannot be expressed in strict
# mode without an explicit mapping. A missing entry for list/any/absent tokens raises at build.
_STRICT_MODE_REFINEMENTS = {
    ("grouping", "member_ids"): {
        "type": "array",
        "items": {"type": "string"},
    },
    ("ruling", "reason"): {
        "type": "string",
    },
}

_CHANNEL_BY_ENGINE = {
    "codex": CHANNEL_NATIVE,
    "cursor": CHANNEL_NATIVE,
    "claude": CHANNEL_NATIVE,
}

RESULT_DELIVERY_ARGV = "argv"      # the shell appends -o <path> --output-schema <schema>
RESULT_DELIVERY_PROMPT = "prompt"  # the shell names <path> in a per-attempt prompt block
RESULT_DELIVERY_STDOUT = "stdout"  # the shell passes --json-schema <schema> on argv; the runner materializes the final result event's structured_output to the result path
_RESULT_DELIVERY_BY_ENGINE = {
    "codex": RESULT_DELIVERY_ARGV,
    "cursor": RESULT_DELIVERY_PROMPT,
    "claude": RESULT_DELIVERY_STDOUT,
}

RESULT_FILE_LINE_PREFIX = "Result file (write exactly this path; nothing else is graded): "

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


class StrictModeViolationError(ValueError):
    """Raised when a schema node violates far-side strict-mode structural rules."""


class UnrefinedTypeTokenError(ValueError):
    """Raised when a list/any/absent token has no strict-mode refinement entry."""


def _strict_context_path(path):
    """Format a schema path like the vendor's invalid_json_schema context tuple."""
    if not path:
        return "()"
    return repr(tuple(path))


def assert_strict_mode_valid(schema, path=()):
    """Walk schema and raise StrictModeViolationError on the first structural violation."""
    if not isinstance(schema, dict):
        raise StrictModeViolationError(
            "In context=%s, schema must be an object"
            % _strict_context_path(path)
        )

    if path == () and schema.get("type") != "object":
        raise StrictModeViolationError(
            "In context=%s, root schema must have type 'object'"
            % _strict_context_path(path)
        )

    if "oneOf" in schema:
        raise StrictModeViolationError(
            "In context=%s, oneOf is not permitted in strict mode"
            % _strict_context_path(path)
        )

    if "anyOf" in schema:
        for index, branch in enumerate(schema["anyOf"]):
            assert_strict_mode_valid(branch, path + ("anyOf", str(index)))
        return

    if "type" not in schema:
        raise StrictModeViolationError(
            "In context=%s, schema must have a 'type' key"
            % _strict_context_path(path)
        )

    type_spec = schema["type"]
    type_names = type_spec if isinstance(type_spec, list) else (type_spec,)

    if "array" in type_names:
        if "items" not in schema:
            raise StrictModeViolationError(
                "In context=%s, array schema missing items"
                % _strict_context_path(path)
            )
        assert_strict_mode_valid(schema["items"], path + ("items",))

    if "object" in type_names:
        if schema.get("additionalProperties") is not False:
            raise StrictModeViolationError(
                "In context=%s, object schema must set additionalProperties to false"
                % _strict_context_path(path)
            )
        props = schema.get("properties") or {}
        required = schema.get("required")
        if required is None:
            raise StrictModeViolationError(
                "In context=%s, object schema missing required list"
                % _strict_context_path(path)
            )
        if set(required) != set(props.keys()):
            missing = sorted(set(props.keys()) - set(required))
            extra = sorted(set(required) - set(props.keys()))
            detail = []
            if missing:
                detail.append("undeclared properties not in required: %s" % ", ".join(missing))
            if extra:
                detail.append("required properties not declared: %s" % ", ".join(extra))
            raise StrictModeViolationError(
                "In context=%s, object required/properties mismatch (%s)"
                % (_strict_context_path(path), "; ".join(detail))
            )
        for name, subschema in props.items():
            assert_strict_mode_valid(subschema, path + ("properties", name))


def channel_for(engine):
    """Return the declared result channel for a registered dispatch engine."""
    if not isinstance(engine, str) or engine not in _CHANNEL_BY_ENGINE:
        raise UnknownEngineError(
            "unknown engine %r; registered engines: %s"
            % (engine, ", ".join(model_registry.vendors()))
        )
    return _CHANNEL_BY_ENGINE[engine]


def result_delivery(engine):
    """How a native-channel engine receives its result path; None for a marker-channel engine."""
    if not isinstance(engine, str) or engine not in _CHANNEL_BY_ENGINE:
        raise UnknownEngineError(
            "unknown engine %r; registered engines: %s"
            % (engine, ", ".join(model_registry.vendors()))
        )
    channel = _CHANNEL_BY_ENGINE[engine]
    if channel == CHANNEL_MARKER:
        return None
    delivery = _RESULT_DELIVERY_BY_ENGINE.get(engine)
    if delivery is None:
        raise ValueError("native engine %r has no result delivery entry" % (engine,))
    return delivery


def file_result_contract(schema_text, result_path, run_kind=RUN_KIND_REVIEW):
    """Prompt block for RESULT_DELIVERY_PROMPT engines: the one file to write and the schema it must match."""
    if run_kind == RUN_KIND_REVIEW:
        edit_clause = (
            "Writing this one file is the sole exception to \"do not edit anything\" — "
            "create no other file and change nothing else. "
        )
    elif run_kind == RUN_KIND_WRITE:
        edit_clause = (
            "Writing this result file is in addition to the repository changes your order asks for; "
            "never add the result file itself to the repository. "
        )
    else:
        raise ValueError(
            "unknown run_kind %r; expected %r or %r"
            % (run_kind, RUN_KIND_REVIEW, RUN_KIND_WRITE)
        )
    return (
        "Typed-file result contract (this run is graded ONLY from the file named on the next line):\n"
        + RESULT_FILE_LINE_PREFIX
        + result_path
        + "\n"
        "Write that one file, containing exactly one JSON object that validates against the declared schema below. "
        + edit_clause
        + "The JSON is graded from the file only: your final chat reply is never read, so do not print the object to stdout; "
        "when the file is written, reply with the single word DONE.\n"
        "Declared schema (JSON Schema; every listed property is required; additionalProperties is false throughout):\n"
        "```json\n"
        + schema_text
        + "\n```\n"
    )


def result_file_path_from_prompt(text):
    """The result path named by the LAST RESULT_FILE_LINE_PREFIX line in text, or None. Never raises."""
    if not isinstance(text, str):
        return None
    path = None
    for line in text.split("\n"):
        if line.startswith(RESULT_FILE_LINE_PREFIX):
            remainder = line[len(RESULT_FILE_LINE_PREFIX):].strip()
            path = remainder if remainder else None
    return path


def declared_schema(engine, run_kind, expected_result_kind=None):
    """Return the JSON Schema dict for this (engine, run-kind), or None on marker channel."""
    if channel_for(engine) == CHANNEL_MARKER:
        return None
    if run_kind == RUN_KIND_REVIEW:
        schema = _review_root_schema(expected_result_kind)
    elif run_kind == RUN_KIND_WRITE:
        schema = _write_root_schema()
    else:
        raise ValueError(
            "unknown run_kind %r; expected %r or %r"
            % (run_kind, RUN_KIND_REVIEW, RUN_KIND_WRITE)
        )
    assert_strict_mode_valid(schema)
    return schema


def _validate_with_detail(schema, value):
    """Validate value against schema. Returns (ok, reason, failure_detail). Never raises."""
    if schema is None:
        return False, "schema is None; marker-channel callers must not reach validate", None
    try:
        _validate(schema, value, "$")
        return True, "", None
    except _ValidationError as exc:
        return False, str(exc), exc.to_detail()


def validate(schema, value):
    """Validate value against schema. Returns (ok, reason). Never raises."""
    ok, reason, _detail = _validate_with_detail(schema, value)
    return ok, reason


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
    if token in ("list", "any"):
        raise UnrefinedTypeTokenError(
            "type token %r requires a strict-mode refinement entry" % (token,)
        )
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
    if token == "object":
        return {"type": "object"}
    if token == "absolute-path":
        return {"type": "string"}
    if token == "list-of-objects":
        return {"type": "array", "items": {"type": "object"}}
    if token == "nullable-list-of-objects":
        return {"type": ["array", "null"], "items": {"type": "object"}}
    raise ValueError("unhandled type token %r" % (token,))


def _strict_schema_for_field(result_kind, field, token, *, optional=False, enums=None):
    """Build a strict-mode schema fragment for one binding field."""
    effective = token if token else "any"
    if effective in ("list", "any"):
        key = (result_kind, field)
        if key not in _STRICT_MODE_REFINEMENTS:
            raise UnrefinedTypeTokenError(
                "no strict-mode refinement for %r field %r (token %r)"
                % (result_kind, field, effective)
            )
        prop = dict(_STRICT_MODE_REFINEMENTS[key])
    else:
        prop = _json_schema_for_type_token(effective)
    if enums:
        prop = dict(prop)
        prop["enum"] = list(enums)
    if optional:
        prop = _nullable_type_schema(prop)
    return prop


def _element_object_schema(elem_contract, result_kind):
    required = list(elem_contract.get("required") or [])
    optional = list(elem_contract.get("optional") or [])
    types = elem_contract.get("types") or {}
    enums = elem_contract.get("enums") or {}
    all_fields = required + optional
    properties = {}
    for field in all_fields:
        prop = _strict_schema_for_field(
            result_kind,
            field,
            types.get(field, "any"),
            optional=field in optional,
            enums=enums.get(field),
        )
        properties[field] = prop
    return {
        "type": "object",
        "additionalProperties": False,
        "required": all_fields,
        "properties": properties,
    }


def _top_level_field_schema(contract, field, *, result_kind, optional_fields=()):
    types = contract.get("types") or {}
    elements = contract.get("elements") or {}
    enums = contract.get("enums") or {}
    tok = types.get(field, "any")
    if tok == "list-of-objects":
        elem = elements.get(field) or {}
        schema = {
            "type": "array",
            "items": _element_object_schema(elem, result_kind),
        }
        if field in optional_fields:
            schema = _nullable_type_schema(schema)
    elif tok == "nullable-list-of-objects":
        elem = elements.get(field) or {}
        schema = {
            "type": ["array", "null"],
            "items": _element_object_schema(elem, result_kind),
        }
    else:
        schema = _strict_schema_for_field(
            result_kind,
            field,
            tok,
            optional=field in optional_fields,
            enums=enums.get(field),
        )
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


def _ruling_branch_fields():
    contract = _phase_contract(payload_contracts.P_AUDITS)
    return list(contract.get("required") or []) + list(contract.get("optional") or ())


def _branch_payload_schema(kind):
    if kind == "findings":
        return {
            "type": "array",
            "items": _finding_member_schema(),
        }
    if kind == "verdicts":
        contract = _phase_contract(payload_contracts.P_VERIFIERS)
        return _top_level_field_schema(contract, "verdicts", result_kind=kind)
    if kind == "grouping":
        contract = _phase_contract(payload_contracts.P_SYNTHESIS)
        return _top_level_field_schema(contract, "grouping", result_kind=kind)
    if kind == "ruling":
        contract = _phase_contract(payload_contracts.P_AUDITS)
        ordered = list(contract.get("required") or []) + list(contract.get("optional") or ())
        optional = set(contract.get("optional") or ())
        properties = {}
        for field in ordered:
            if field == "newIssues":
                properties[field] = _nullable_type_schema({
                    "type": "array",
                    "items": _finding_member_schema(),
                })
            else:
                properties[field] = _top_level_field_schema(
                    contract, field, result_kind=kind, optional_fields=optional)
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
    ruling_fields = _ruling_branch_fields()
    if kind == "ruling":
        ruling_props = payload_schema["properties"]
        for field in ruling_fields:
            properties[field] = ruling_props[field]
            required.append(field)
    else:
        for field in ruling_fields:
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
    def __init__(self, message, *, kind=None, path=None, got_type=None, sub_failures=None):
        super().__init__(message)
        self.kind = kind
        self.path = path
        self.got_type = got_type
        self.sub_failures = sub_failures

    def to_detail(self):
        detail = {"kind": self.kind, "path": self.path}
        if self.got_type is not None:
            detail["got_type"] = self.got_type
        if self.sub_failures is not None:
            detail["sub_failures"] = self.sub_failures
        return detail


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
        raise _ValidationError(
            "%s: schema must be an object" % path,
            kind="type-mismatch",
            path=path,
        )
    unknown = set(schema) - _ALLOWED_SCHEMA_KEYWORDS
    if unknown:
        raise _ValidationError(
            "%s: unknown schema keyword(s): %s"
            % (path, ", ".join(sorted(unknown))),
            kind="schema-error",
            path=path,
        )

    if "anyOf" in schema:
        failures = []
        failure_details = []
        for index, branch in enumerate(schema["anyOf"]):
            try:
                _validate(branch, value, "%s.anyOf[%d]" % (path, index))
                return
            except _ValidationError as exc:
                failures.append(str(exc))
                failure_details.append(exc.to_detail())
        raise _ValidationError(
            "%s: anyOf failed (%d branches): %s"
            % (path, len(failures), "; ".join(failures)),
            kind="any-of-failed",
            path=path,
            sub_failures=failure_details,
        )

    if "type" in schema and not _type_matches(schema["type"], value):
        raise _ValidationError(
            "%s: expected type %r, got %s"
            % (path, schema["type"], type(value).__name__),
            kind="type-mismatch",
            path=path,
            got_type=type(value).__name__,
        )

    if "enum" in schema and value not in schema["enum"]:
        raise _ValidationError(
            "%s: value %r not in enum %r" % (path, value, schema["enum"]),
            kind="enum-mismatch",
            path=path,
        )

    if isinstance(value, dict):
        if schema.get("additionalProperties") is False:
            allowed = set((schema.get("properties") or {}).keys())
            extra = set(value) - allowed
            if extra:
                raise _ValidationError(
                    "%s: additional properties forbidden: %s"
                    % (path, ", ".join(sorted(extra))),
                    kind="additional-properties",
                    path=path,
                )
        for req in schema.get("required") or []:
            if req not in value:
                raise _ValidationError(
                    "%s: missing required property %r" % (path, req),
                    kind="missing-required",
                    path=path,
                )
        props = schema.get("properties") or {}
        for key, subschema in props.items():
            if key in value:
                _validate(subschema, value[key], "%s.%s" % (path, key))
    elif isinstance(value, list) and "items" in schema:
        item_schema = schema["items"]
        for index, item in enumerate(value):
            _validate(item_schema, item, "%s[%d]" % (path, index))


def _schema_result_branches(result_schema):
    """Return the declared review branch schemas under ``result``. Never raises."""
    if not isinstance(result_schema, dict):
        return []
    if "anyOf" in result_schema:
        branches = result_schema.get("anyOf")
        return list(branches) if isinstance(branches, list) else []
    return [result_schema]


def _schema_branch_kind(branch):
    """Return the single ``resultKind`` enum value for a branch schema. Never raises."""
    if not isinstance(branch, dict):
        return None
    props = branch.get("properties") or {}
    rk = props.get("resultKind") or {}
    enum = rk.get("enum") or []
    if enum and isinstance(enum[0], str):
        return enum[0]
    return None


def _schema_property_is_null_only(subschema):
    if not isinstance(subschema, dict):
        return False
    type_spec = subschema.get("type")
    if type_spec == "null":
        return True
    if isinstance(type_spec, list) and type_spec == ["null"]:
        return True
    return False


def _schema_branch_active_payload_keys(branch):
    """Payload property names populated on this branch (not the null-only slots). Never raises."""
    if not isinstance(branch, dict):
        return []
    props = branch.get("properties") or {}
    active = []
    for key, subschema in props.items():
        if key in ("resultKind", "investigated"):
            continue
        if _schema_property_is_null_only(subschema):
            continue
        active.append(key)
    return active


def native_review_payload_shape(detail, envelope=None, branch=None):
    """Derive payloadShape for a native-channel review forfeit from the result file state.

    Returns {"parsed", "topLevelKeys", "keysTruncated"} or None when no diagnostic applies.
    Never raises. Marker tokens are the engine_adapter SHAPE_* home — imported lazily so this
    module stays free of engine_adapter at import time.
    """
    import engine_adapter as ea  # noqa: PLC0415 — lazy: avoids import cycle with engine_dispatch

    if detail in ("native-result-missing",):
        return {
            "parsed": ea.SHAPE_EMPTY_STDOUT,
            "topLevelKeys": [],
            "keysTruncated": False,
        }
    if detail in ("native-result-malformed",):
        return {
            "parsed": ea.SHAPE_NO_PARSEABLE_JSON,
            "topLevelKeys": [],
            "keysTruncated": False,
        }
    if detail in ("native-result-schema-invalid", "native-result-malformed-branch"):
        if isinstance(branch, dict):
            matched = ea._recognised_review_kinds(branch)
            top_keys, keys_truncated = ea._bound_top_level_keys(branch)
            if len(matched) > 1:
                return {
                    "parsed": ea.SHAPE_OBJECT_BOTH_PAYLOAD_KEYS,
                    "topLevelKeys": top_keys,
                    "keysTruncated": keys_truncated,
                }
            return {
                "parsed": ea.SHAPE_OBJECT_WITHOUT_FINDINGS,
                "topLevelKeys": top_keys,
                "keysTruncated": keys_truncated,
            }
        if isinstance(envelope, dict):
            top_keys, keys_truncated = ea._bound_top_level_keys(envelope)
            return {
                "parsed": ea.SHAPE_OBJECT_WITHOUT_FINDINGS,
                "topLevelKeys": top_keys,
                "keysTruncated": keys_truncated,
            }
        return {
            "parsed": ea.SHAPE_OBJECT_WITHOUT_FINDINGS,
            "topLevelKeys": [],
            "keysTruncated": False,
        }
    return None


def write_result_contract_from_schema(schema, delivery=None):
    """Derive native-channel write prompt contract prose from a declared schema dict."""
    if not isinstance(schema, dict):
        return ""
    required = schema.get("required") or []
    req_list = ", ".join("`%s`" % k for k in required)
    if delivery == RESULT_DELIVERY_PROMPT:
        graded_line = (
            "The graded result is the JSON object you write to the result file named in the typed-file "
            "contract at the end of this prompt; it must match the declared output schema."
        )
    elif delivery == RESULT_DELIVERY_STDOUT:
        graded_line = (
            "The graded result is your structured output — the typed final response the --json-schema "
            "flag governs; it is the report object matching the declared schema. "
            "Print nothing else as a result; stdout is telemetry."
        )
    else:
        graded_line = "The final response must be exactly one JSON object matching the declared output schema."
    lines = [
        "Write result contract (your graded result file must match the declared output schema):",
        graded_line,
        "Root required properties: %s." % req_list,
        "`report` is a non-blank plain-language summary of what was done and the receipts "
        "observed; an empty `report` is refused.",
        engine_adapter.WRITE_REPORT_FIELD_SEMANTICS.rstrip("\n"),
    ]
    return "\n".join(lines) + "\n"


def review_result_contract_from_schema(schema, delivery=None):
    """Derive native-channel review prompt contract prose from a declared schema dict."""
    if not isinstance(schema, dict):
        return ""
    result_schema = (schema.get("properties") or {}).get("result")
    branches = _schema_result_branches(result_schema)
    kinds = []
    for branch in branches:
        kind = _schema_branch_kind(branch)
        if kind is not None:
            kinds.append(kind)
    if not kinds:
        return ""
    kind_list = ", ".join("`%s`" % k for k in kinds)
    if delivery == RESULT_DELIVERY_PROMPT:
        result_line = (
            "The graded result is the JSON object you write to the result file named in the typed-file "
            "contract at the end of this prompt; its root has exactly one property `result` wrapping the graded branch."
        )
    elif delivery == RESULT_DELIVERY_STDOUT:
        result_line = (
            "The graded result is your structured output — the typed final response the --json-schema flag governs; "
            "its root has exactly one property `result` wrapping the graded branch. "
            "Print nothing else as a result; stdout is telemetry."
        )
    else:
        result_line = (
            "Write a JSON object whose root has exactly one property `result` wrapping the graded branch."
        )
    lines = [
        "Review result contract (your graded result file must match the declared schema):",
        result_line,
        "The declared envelope is a root object whose single `result` property holds the branch.",
        "`resultKind` on that branch names which result kind this run carries (%s)."
        % kind_list,
        "Every other payload property on the branch must be JSON null — only the named kind's "
        "payload may be populated.",
        "`investigated` lists the repository paths you actually read while forming this result.",
    ]
    for branch in branches:
        kind = _schema_branch_kind(branch)
        if kind is None:
            continue
        active = _schema_branch_active_payload_keys(branch)
        if not active:
            continue
        prop_list = ", ".join("`%s`" % k for k in active)
        lines.append(
            "  - `%s`: populate %s; set every other payload property to null."
            % (kind, prop_list)
        )
    return "\n".join(lines) + "\n"
