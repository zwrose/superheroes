"""Behaviour tests for engine_result_channel (#1270 WO-A)."""
import copy
import importlib.util
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_HERE, "..")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

try:
    import jsonschema
except ImportError:
    jsonschema = None


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ERC = _load("engine_result_channel")
MR = _load("model_registry")
PC = _load("payload_contracts")
RFS = _load("review_findings_schema")
EA = _load("engine_adapter")


def _is_object_schema_node(node):
    if not isinstance(node, dict):
        return False
    if node.get("type") == "object":
        return True
    if isinstance(node.get("properties"), dict):
        return True
    return False


def _iter_object_schemas(node, path="$"):
    if not isinstance(node, dict):
        return
    if _is_object_schema_node(node):
        yield path, node
    if "oneOf" in node:
        pytest.fail("schema contains forbidden oneOf at %s" % path)
    props = node.get("properties")
    if isinstance(props, dict):
        for name, sub in props.items():
            yield from _iter_object_schemas(sub, "%s.properties.%s" % (path, name))
    items = node.get("items")
    if isinstance(items, dict):
        yield from _iter_object_schemas(items, "%s.items" % path)
    for branch in node.get("anyOf") or ():
        yield from _iter_object_schemas(branch, "%s.anyOf" % path)


def _example_finding_member():
    member = {}
    for key in RFS.CANONICAL_MEMBER_KEYS:
        schema = RFS.FINDING_PROPERTY_SCHEMAS[key]
        if "enum" in schema:
            member[key] = next(v for v in schema["enum"] if v is not None)
        elif schema.get("type") == ["integer", "null"]:
            member[key] = None
        elif schema.get("type") == ["boolean", "null"]:
            member[key] = None
        elif schema.get("type") == ["string", "null"]:
            member[key] = "example"
        else:
            member[key] = "example"
    return member


def _valid_review_branch(kind):
    investigated = ["path/to/file.py"]
    if kind == "findings":
        return {
            "resultKind": "findings",
            "findings": [_example_finding_member()],
            "verdicts": None,
            "grouping": None,
            "id": None,
            "ruling": None,
            "reason": None,
            "newIssues": None,
            "evidence": None,
            "auditorVendor": None,
            "investigated": investigated,
        }
    if kind == "verdicts":
        contract, _ = PC.payload_contract(PC.P_VERIFIERS)
        elem = contract["elements"]["verdicts"]
        verdict = {}
        for field in list(elem.get("required") or []) + list(elem.get("optional") or ()):
            if field == "verdict":
                verdict[field] = elem["enums"]["verdict"][0]
            elif field == "id":
                verdict[field] = "finding-001"
            else:
                verdict[field] = None
        return {
            "resultKind": "verdicts",
            "findings": None,
            "verdicts": [verdict],
            "grouping": None,
            "id": None,
            "ruling": None,
            "reason": None,
            "newIssues": None,
            "evidence": None,
            "auditorVendor": None,
            "investigated": investigated,
        }
    if kind == "grouping":
        return {
            "resultKind": "grouping",
            "findings": None,
            "verdicts": None,
            "grouping": [{"member_ids": ["a-001", "b-002"]}],
            "id": None,
            "ruling": None,
            "reason": None,
            "newIssues": None,
            "evidence": None,
            "auditorVendor": None,
            "investigated": investigated,
        }
    contract, _ = PC.payload_contract(PC.P_AUDITS)
    ruling = {"id": "audit-seat", "ruling": contract["enums"]["ruling"][0], "reason": "grounds"}
    for opt in contract.get("optional") or ():
        ruling[opt] = None
    return {
        "resultKind": "ruling",
        "findings": None,
        "verdicts": None,
        "grouping": None,
        "investigated": investigated,
        **ruling,
    }


def _wrap_result(branch):
    return {"result": branch}


@pytest.mark.parametrize("vendor,expected", [
    ("codex", ERC.CHANNEL_NATIVE),
    ("cursor", ERC.CHANNEL_MARKER),
    ("claude", ERC.CHANNEL_MARKER),
])
def test_channel_for_registered_engines(vendor, expected):
    assert ERC.channel_for(vendor) == expected


@pytest.mark.parametrize("bad", ["bogus", None, 7, ""])
def test_channel_for_unknown_engine_refuses(bad):
    with pytest.raises(ERC.UnknownEngineError):
        ERC.channel_for(bad)


def test_channel_engine_set_matches_registry_vendors():
    mapped = frozenset(ERC._CHANNEL_BY_ENGINE)
    assert mapped == frozenset(MR.vendors())


def test_review_schema_root_and_strict_mode_tree():
    schema = ERC.declared_schema("codex", ERC.RUN_KIND_REVIEW)
    assert schema["type"] == "object"
    for path, node in _iter_object_schemas(schema):
        if "oneOf" in node:
            pytest.fail("oneOf at %s" % path)
        if _is_object_schema_node(node):
            assert node.get("additionalProperties") is False, path
            props = node.get("properties") or {}
            required = node.get("required") or []
            assert set(required) == set(props.keys()), "%s required mismatch" % path


@pytest.mark.parametrize("kind", ERC.REVIEW_RESULT_KINDS)
def test_review_discrimination_valid_branch_passes(kind):
    schema = ERC.declared_schema("codex", ERC.RUN_KIND_REVIEW)
    ok, reason = ERC.validate(schema, _wrap_result(_valid_review_branch(kind)))
    assert ok, reason


@pytest.mark.parametrize("kind", ERC.REVIEW_RESULT_KINDS)
def test_review_discrimination_wrong_payload_key_fails(kind):
    schema = ERC.declared_schema("codex", ERC.RUN_KIND_REVIEW)
    branch = _valid_review_branch(kind)
    other = next(k for k in ERC.REVIEW_RESULT_KINDS if k != kind and k != "ruling")
    if other in branch:
        branch[other] = _valid_review_branch(other)[other]
    ok, reason = ERC.validate(schema, _wrap_result(branch))
    assert not ok
    assert reason


def test_review_narrowing_single_branch():
    schema = ERC.declared_schema(
        "codex", ERC.RUN_KIND_REVIEW, expected_result_kind="findings")
    result = schema["properties"]["result"]
    assert "anyOf" not in result
    assert result["properties"]["resultKind"]["enum"] == ["findings"]
    ok, _ = ERC.validate(schema, _wrap_result(_valid_review_branch("findings")))
    assert ok
    wrong = _wrap_result(_valid_review_branch("verdicts"))
    ok, reason = ERC.validate(schema, wrong)
    assert not ok
    assert reason


def _branch_property_schema(kind):
    schema = ERC.declared_schema("codex", ERC.RUN_KIND_REVIEW, expected_result_kind=kind)
    return schema["properties"]["result"]


def _binding_field_names(phase, field):
    contract, reason = PC.payload_contract(phase)
    assert reason is None
    if field == "ruling":
        return list((contract.get("required") or []) + (contract.get("optional") or ()))
    elem = contract["elements"][field]
    return list((elem.get("required") or []) + list(elem.get("optional") or ()))


def _binding_enums(phase, field, elem_field):
    contract, _ = PC.payload_contract(phase)
    if field == "ruling":
        return contract.get("enums", {}).get(elem_field)
    return contract["elements"][field].get("enums", {}).get(elem_field)


@pytest.mark.parametrize("phase,field,kind", [
    (PC.P_VERIFIERS, "verdicts", "verdicts"),
    (PC.P_SYNTHESIS, "grouping", "grouping"),
    (PC.P_AUDITS, "ruling", "ruling"),
])
def test_generated_branch_tracks_payload_contracts(phase, field, kind):
    branch = _branch_property_schema(kind)
    expected_fields = _binding_field_names(phase, field)
    if kind == "ruling":
        props = branch["properties"]
        for fname in expected_fields:
            assert fname in props
            if fname in (PC.payload_contract(phase)[0].get("enums") or {}):
                assert props[fname]["enum"] == list(
                    PC.payload_contract(phase)[0]["enums"][fname])
    else:
        items = branch["properties"][field]
        if field == "grouping":
            item_props = items["items"]["properties"]
            expected_fields = _binding_field_names(phase, field)
            for fname in expected_fields:
                assert fname in item_props
        else:
            item_props = items["items"]["properties"]
            for fname in expected_fields:
                assert fname in item_props
                enum = _binding_enums(phase, field, fname)
                if enum is not None:
                    assert item_props[fname]["enum"] == list(enum)


@pytest.mark.parametrize("token", sorted(PC.TYPE_TOKENS))
def test_every_type_token_handled(token):
    ERC._json_schema_for_type_token(token)


def test_unrecognised_type_token_raises():
    with pytest.raises(ValueError, match="unknown type token"):
        ERC._json_schema_for_type_token("not-a-real-token")


def test_write_schema_matches_grade_build_report():
    schema = ERC.declared_schema("codex", ERC.RUN_KIND_WRITE)
    assert set(schema["required"]) == {"ok", "signal", "report", "evidence"}
    assert schema["properties"]["signal"]["enum"] == list(ERC.WRITE_SIGNAL_ENUM)
    specimen = {
        "ok": True,
        "signal": "ok",
        "report": "full prose report",
        "evidence": {"testFailed": False, "testPassed": True},
    }
    ok, reason = ERC.validate(schema, specimen)
    assert ok, reason
    graded = EA._grade_build_report_obj(specimen)
    assert graded["ok"] is True
    assert graded["signal"] == "ok"


def test_checker_additional_properties_rejects_extra_key():
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["a"],
        "properties": {"a": {"type": "string"}},
    }
    ok, reason = ERC.validate(schema, {"a": "x", "b": 1})
    assert not ok
    assert "additional properties forbidden" in reason


def test_checker_nullable_type_array():
    schema = {"type": ["string", "null"]}
    assert ERC.validate(schema, "x")[0]
    assert ERC.validate(schema, None)[0]
    ok, reason = ERC.validate(schema, 1)
    assert not ok
    assert reason


def test_checker_anyof_picks_branch():
    schema = {
        "anyOf": [
            {"type": "string", "enum": ["a"]},
            {"type": "integer"},
        ]
    }
    assert ERC.validate(schema, "a")[0]
    assert ERC.validate(schema, 3)[0]
    ok, reason = ERC.validate(schema, True)
    assert not ok
    assert "anyOf failed" in reason


def test_checker_unknown_keyword_raises():
    schema = {"type": "string", "minLength": 1}
    ok, reason = ERC.validate(schema, "x")
    assert not ok
    assert "unknown schema keyword" in reason


def _mutate_specimens(valid):
    specimens = []
    specimens.append((valid, True))
    extra = copy.deepcopy(valid)
    extra["extra"] = True
    specimens.append((extra, False))
    if isinstance(valid, dict):
        for key, value in list(valid.items()):
            if value is None:
                bad = copy.deepcopy(valid)
                bad[key] = "not-null"
                specimens.append((bad, False))
            elif isinstance(value, bool):
                bad = copy.deepcopy(valid)
                bad[key] = "not-bool"
                specimens.append((bad, False))
        if valid:
            missing = copy.deepcopy(valid)
            drop = next(iter(missing))
            del missing[drop]
            specimens.append((missing, False))
    return specimens


@pytest.mark.skipif(jsonschema is None, reason="jsonschema not installed")
@pytest.mark.parametrize("run_kind", [ERC.RUN_KIND_REVIEW, ERC.RUN_KIND_WRITE])
def test_differential_agreement_with_jsonschema(run_kind):
    if run_kind == ERC.RUN_KIND_REVIEW:
        schema = ERC.declared_schema("codex", ERC.RUN_KIND_REVIEW)
        valid = _wrap_result(_valid_review_branch("findings"))
        wrong_branch = _wrap_result(_valid_review_branch("verdicts"))
        specimens = _mutate_specimens(valid)
        specimens.append((wrong_branch, False))
    else:
        schema = ERC.declared_schema("codex", ERC.RUN_KIND_WRITE)
        valid = {
            "ok": False,
            "signal": "plan_wrong",
            "report": "stopped",
            "evidence": {"testFailed": True, "testPassed": False},
        }
        specimens = _mutate_specimens(valid)
    for value, _ in specimens:
        ours_ok, ours_reason = ERC.validate(schema, value)
        try:
            jsonschema.validate(value, schema)
            js_ok = True
            js_reason = ""
        except jsonschema.ValidationError as exc:
            js_ok = False
            js_reason = exc.message
        assert ours_ok == js_ok, (
            "disagreement on %r: ours=%s (%r) jsonschema=%s (%r)"
            % (value, ours_ok, ours_reason, js_ok, js_reason)
        )


def test_marker_channel_declared_schema_is_none():
    assert ERC.declared_schema("cursor", ERC.RUN_KIND_REVIEW) is None
    assert ERC.declared_schema("cursor", ERC.RUN_KIND_WRITE) is None
