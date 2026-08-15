"""Canonical review-findings schema guards (#949 WO-2)."""
import importlib.util
import json
import os
import re

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_HERE, "..")
_PLUGIN = os.path.join(_HERE, "..", "..")
_RUBRIC = os.path.join(_PLUGIN, "rubric", "review-base.md")


def _load_review_findings_schema():
    spec = importlib.util.spec_from_file_location(
        "review_findings_schema", os.path.join(_LIB, "review_findings_schema.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RFS = _load_review_findings_schema()


def _load_shipped_schema():
    with open(RFS.review_findings_schema_path(), encoding="utf-8") as fh:
        return json.load(fh)


def _is_object_schema_node(node):
    if not isinstance(node, dict):
        return False
    if node.get("type") == "object":
        return True
    if isinstance(node.get("properties"), dict):
        return True
    if isinstance(node.get("patternProperties"), dict):
        return True
    return False


def _iter_object_schemas(node, path="$"):
    """Yield (path, schema_node) for every JSON Schema object-typed level."""
    if not isinstance(node, dict):
        return
    if _is_object_schema_node(node):
        yield path, node
    props = node.get("properties")
    if isinstance(props, dict):
        for name, sub in props.items():
            yield from _iter_object_schemas(sub, "%s.properties.%s" % (path, name))
    pattern_props = node.get("patternProperties")
    if isinstance(pattern_props, dict):
        for name, sub in pattern_props.items():
            yield from _iter_object_schemas(sub, "%s.patternProperties.%s" % (path, name))
    for keyword in ("$defs", "definitions"):
        defs = node.get(keyword)
        if isinstance(defs, dict):
            for name, sub in defs.items():
                yield from _iter_object_schemas(sub, "%s.%s.%s" % (path, keyword, name))
    items = node.get("items")
    if isinstance(items, dict):
        yield from _iter_object_schemas(items, "%s.items" % path)
    elif isinstance(items, list):
        for index, sub in enumerate(items):
            yield from _iter_object_schemas(sub, "%s.items[%d]" % (path, index))
    for keyword in ("oneOf", "anyOf", "allOf"):
        variants = node.get(keyword)
        if isinstance(variants, list):
            for index, variant in enumerate(variants):
                yield from _iter_object_schemas(variant, "%s.%s[%d]" % (path, keyword, index))
    for keyword in ("if", "then", "else"):
        branch = node.get(keyword)
        if isinstance(branch, dict):
            yield from _iter_object_schemas(branch, "%s.%s" % (path, keyword))
    for keyword in ("not", "additionalItems", "contains", "propertyNames"):
        branch = node.get(keyword)
        if isinstance(branch, dict):
            yield from _iter_object_schemas(branch, "%s.%s" % (path, keyword))
    ap = node.get("additionalProperties")
    if isinstance(ap, dict):
        yield from _iter_object_schemas(ap, "%s.additionalProperties" % path)


def _assert_object_schema_strict(obj_path, obj_schema):
    props = obj_schema.get("properties", {})
    if not isinstance(props, dict):
        props = {}
    assert obj_schema.get("additionalProperties") is False, obj_path
    required = obj_schema.get("required")
    assert isinstance(required, list), obj_path
    assert set(required) == set(props.keys()), obj_path


def _parse_severities_from_rubric(text):
    match = re.search(r'"severity":\s*"([^"]+)"', text)
    assert match, "review-base.md: severity example line not found"
    return {part.strip() for part in match.group(1).split("|")}


def _parse_dimensions_from_rubric(text):
    start = text.index("**Dimensions**")
    end = text.index(". The crew carries", start)
    block = text[start:end]
    return set(re.findall(r"`([^`]+)`", block))


def _parse_finding_keys_from_rubric(text):
    start = text.index("```json")
    end = text.index("```", start + 7)
    block = text[start + 7:end].strip()
    examples = json.loads(block)
    assert isinstance(examples, list) and examples, "rubric: findings JSON example not a non-empty array"
    finding = examples[0]
    assert isinstance(finding, dict), "rubric: first findings example is not an object"
    return set(finding.keys())


def _parse_confidence_enum_from_rubric(text):
    match = re.search(r'"confidence":\s*"([^"]+)"', text)
    assert match, "review-base.md: confidence example line not found"
    return {part.strip() for part in match.group(1).split("|")}


def test_every_object_level_is_strict_mode_complete():
    schema = _load_shipped_schema()
    seen = list(_iter_object_schemas(schema))
    assert seen, "schema walk found no object levels"
    for obj_path, obj_schema in seen:
        _assert_object_schema_strict(obj_path, obj_schema)


def test_schema_walker_rejects_non_strict_nested_fixture():
    non_strict = {
        "type": "object",
        "additionalProperties": False,
        "required": ["findings"],
        "properties": {
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"id": {"type": "string"}},
                    "required": ["id"],
                },
            },
        },
    }
    failures = []
    for obj_path, obj_schema in _iter_object_schemas(non_strict):
        try:
            _assert_object_schema_strict(obj_path, obj_schema)
        except AssertionError:
            failures.append(obj_path)
    assert "$.properties.findings.items" in failures


def _non_strict_nested_fixture(keyword):
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["wrapper"],
        "properties": {
            "wrapper": {
                keyword: {
                    "type": "object",
                    "properties": {"id": {"type": "string"}},
                    "required": ["id"],
                },
            },
        },
    }


@pytest.mark.parametrize(
    "keyword",
    ["not", "additionalItems", "contains", "propertyNames"],
    ids=["not", "additionalItems", "contains", "propertyNames"],
)
def test_schema_walker_rejects_non_strict_nested_fixture_per_keyword(keyword):
    non_strict = _non_strict_nested_fixture(keyword)
    failures = []
    for obj_path, obj_schema in _iter_object_schemas(non_strict):
        try:
            _assert_object_schema_strict(obj_path, obj_schema)
        except AssertionError:
            failures.append(obj_path)
    assert "$.properties.wrapper.%s" % keyword in failures


def test_schema_enums_match_rubric_review_base():
    with open(_RUBRIC, encoding="utf-8") as fh:
        rubric = fh.read()
    rubric_severities = _parse_severities_from_rubric(rubric)
    rubric_dimensions = _parse_dimensions_from_rubric(rubric)
    rubric_finding_keys = _parse_finding_keys_from_rubric(rubric)
    rubric_confidence = _parse_confidence_enum_from_rubric(rubric)

    schema = _load_shipped_schema()
    finding = schema["properties"]["findings"]["items"]["properties"]
    schema_severities = set(finding["severity"]["enum"])
    schema_dimensions = set(finding["dimension"]["enum"])
    schema_finding_keys = set(finding.keys())
    schema_confidence = {v for v in finding["confidence"]["enum"] if v is not None}

    assert schema_severities == rubric_severities
    assert schema_dimensions == rubric_dimensions
    assert schema_finding_keys == rubric_finding_keys
    assert schema_confidence == rubric_confidence


def test_resolver_returns_existing_shipped_schema_path():
    path = RFS.review_findings_schema_path()
    assert path == RFS.REVIEW_FINDINGS_SCHEMA_PATH
    assert os.path.isfile(path)
    assert path.endswith(RFS.REVIEW_FINDINGS_SCHEMA_REL)


def test_resolver_does_not_raise_when_path_missing(tmp_path, monkeypatch):
    missing = str(tmp_path / "missing-schema.json")
    monkeypatch.setattr(RFS, "REVIEW_FINDINGS_SCHEMA_PATH", missing)
    assert RFS.review_findings_schema_path() == missing
    assert not os.path.isfile(missing)
