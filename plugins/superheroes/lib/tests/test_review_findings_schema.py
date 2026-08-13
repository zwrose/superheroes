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


def _load_engine_dispatch():
    spec = importlib.util.spec_from_file_location(
        "engine_dispatch", os.path.join(_LIB, "engine_dispatch.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_review_findings_schema():
    spec = importlib.util.spec_from_file_location(
        "review_findings_schema", os.path.join(_LIB, "review_findings_schema.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ED = _load_engine_dispatch()
RFS = _load_review_findings_schema()


def _load_shipped_schema():
    with open(RFS.review_findings_schema_path(), encoding="utf-8") as fh:
        return json.load(fh)


def _iter_object_schemas(node, path="$"):
    """Yield (path, schema_node) for every JSON Schema object that declares properties."""
    if not isinstance(node, dict):
        return
    props = node.get("properties")
    if isinstance(props, dict):
        yield path, node
        for name, sub in props.items():
            yield from _iter_object_schemas(sub, "%s.properties.%s" % (path, name))
    items = node.get("items")
    if isinstance(items, dict):
        yield from _iter_object_schemas(items, "%s.items" % path)
    for keyword in ("oneOf", "anyOf", "allOf"):
        variants = node.get(keyword)
        if isinstance(variants, list):
            for index, variant in enumerate(variants):
                yield from _iter_object_schemas(variant, "%s.%s[%d]" % (path, keyword, index))
    ap = node.get("additionalProperties")
    if isinstance(ap, dict):
        yield from _iter_object_schemas(ap, "%s.additionalProperties" % path)


def _parse_severities_from_rubric(text):
    match = re.search(r'"severity":\s*"([^"]+)"', text)
    assert match, "review-base.md: severity example line not found"
    return {part.strip() for part in match.group(1).split("|")}


def _parse_dimensions_from_rubric(text):
    start = text.index("**Dimensions**")
    end = text.index(". The crew carries", start)
    block = text[start:end]
    return set(re.findall(r"`([^`]+)`", block))


def test_every_object_level_is_strict_mode_complete():
    schema = _load_shipped_schema()
    seen = list(_iter_object_schemas(schema))
    assert seen, "schema walk found no object levels with properties"
    for obj_path, obj_schema in seen:
        props = obj_schema.get("properties", {})
        assert obj_schema.get("additionalProperties") is False, obj_path
        required = obj_schema.get("required")
        assert isinstance(required, list), obj_path
        assert set(required) == set(props.keys()), obj_path


def test_canonical_schema_passes_validate_review_schema_path():
    ok, detail = ED._validate_review_schema_path(RFS.review_findings_schema_path())
    assert ok is True
    assert detail is None


def test_schema_enums_match_rubric_review_base():
    with open(_RUBRIC, encoding="utf-8") as fh:
        rubric = fh.read()
    rubric_severities = _parse_severities_from_rubric(rubric)
    rubric_dimensions = _parse_dimensions_from_rubric(rubric)

    schema = _load_shipped_schema()
    finding = schema["properties"]["findings"]["items"]["properties"]
    schema_severities = set(finding["severity"]["enum"])
    schema_dimensions = set(finding["dimension"]["enum"])

    assert schema_severities == rubric_severities
    assert schema_dimensions == rubric_dimensions


def test_resolver_returns_existing_shipped_schema_path():
    path = RFS.review_findings_schema_path()
    assert path == RFS.REVIEW_FINDINGS_SCHEMA_PATH
    assert os.path.isfile(path)
    assert path.endswith(os.path.join("schemas", "review-findings.schema.json"))


def test_validate_review_schema_path_refusal_tokens_unchanged(tmp_path):
    missing_ok, missing_detail = ED._validate_review_schema_path(str(tmp_path / "absent.json"))
    assert missing_ok is False
    assert missing_detail == ED.SCHEMA_REFUSAL_MISSING

    unreadable = tmp_path / "bad.json"
    unreadable.write_text("{not json", encoding="utf-8")
    unreadable_ok, unreadable_detail = ED._validate_review_schema_path(str(unreadable))
    assert unreadable_ok is False
    assert unreadable_detail == ED.SCHEMA_REFUSAL_UNREADABLE

    not_shaped = tmp_path / "not-shaped.json"
    not_shaped.write_text(json.dumps({"type": "object", "properties": {"verdicts": {}}}), encoding="utf-8")
    shaped_ok, shaped_detail = ED._validate_review_schema_path(str(not_shaped))
    assert shaped_ok is False
    assert shaped_detail == ED.SCHEMA_REFUSAL_NOT_FINDINGS_SHAPED


def test_resolver_does_not_raise_when_path_missing(tmp_path, monkeypatch):
    missing = str(tmp_path / "missing-schema.json")
    monkeypatch.setattr(RFS, "REVIEW_FINDINGS_SCHEMA_PATH", missing)
    assert RFS.review_findings_schema_path() == missing
    assert not os.path.isfile(missing)
