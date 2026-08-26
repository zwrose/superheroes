"""Canonical review-findings schema guards (#949 WO-2, #1145 WO-A)."""
import ast
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


def _schema_finding_properties():
    with open(RFS.review_findings_schema_path(), encoding="utf-8") as fh:
        schema = json.load(fh)
    return schema["properties"]["findings"]["items"]["properties"]


def _schema_severity_enum():
    return _schema_finding_properties()["severity"]["enum"]


def _reload_rfs_module(schema_path=None):
    spec = importlib.util.spec_from_file_location(
        "review_findings_schema_reload_%s" % (schema_path or "default"),
        os.path.join(_LIB, "review_findings_schema.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if schema_path is not None:
        mod.REVIEW_FINDINGS_SCHEMA_PATH = schema_path
        mod._init_schema_constants()
    return mod


def test_canonical_member_keys_match_schema_independently():
    # axis: canonical member keys are read from the shipped schema, not hand-copied
    schema_keys = tuple(_schema_finding_properties().keys())
    assert RFS.CANONICAL_MEMBER_KEYS == schema_keys


def test_schema_read_success_no_fallback():
    assert RFS.SCHEMA_READ_USED_FALLBACK is False


def test_schema_read_failure_uses_literal_fallback(tmp_path):
    missing = str(tmp_path / "missing-schema.json")
    mod = _reload_rfs_module(schema_path=missing)
    assert mod.SCHEMA_READ_USED_FALLBACK is True
    assert mod.CANONICAL_MEMBER_KEYS == mod._FALLBACK_CANONICAL_MEMBER_KEYS
    assert mod.SEVERITY_TIERS == mod._FALLBACK_SEVERITY_TIERS


def test_substance_keys_canonical_subset_of_member_keys():
    assert RFS.SUBSTANCE_KEYS_CANONICAL <= set(RFS.CANONICAL_MEMBER_KEYS)


def test_severity_tiers_match_schema_and_engine_adapter():
    # axis: severity tiers are schema-derived and match engine_adapter until WO-B re-points
    import engine_adapter as EA

    schema_tiers = frozenset(_schema_severity_enum())
    assert RFS.SEVERITY_TIERS == schema_tiers
    assert RFS.SEVERITY_TIERS == EA.REVIEW_SEVERITY_TIERS


def test_review_findings_schema_import_cycle_pin():
    # axis: declared home stays below engine_adapter and round_orders — no upward imports
    with open(os.path.join(_LIB, "review_findings_schema.py"), encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename="review_findings_schema.py")
    forbidden = {"engine_adapter", "round_orders", "payload_contracts"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                assert root not in forbidden
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root = node.module.split(".")[0]
                assert root not in forbidden


@pytest.mark.parametrize(
    "bad_severity",
    [None, "", "critical", 0, True, "Bogus"],
    ids=["null", "empty", "lowercase", "zero", "true", "off-scale-string"],
)
def test_member_is_engaged_off_scale_severity_fails_leg_b(bad_severity):
    # axis: leg (b) requires enum membership, not mere severity presence
    member = {"severity": bad_severity, "defect": "real censused prose"}
    assert RFS.member_is_engaged(member) is False


def test_member_carries_sentinel_true_for_example_member():
    # axis: two-or-more placeholder field values refuse verbatim example echo
    example = RFS.example_findings_object()["findings"][0]
    assert RFS.member_carries_sentinel(example) is True


def test_member_carries_sentinel_true_for_near_copy():
    # axis: near-copy with plausible id/severity but other fields still exact placeholders
    example = RFS.example_findings_object()["findings"][0]
    near_copy = dict(example)
    near_copy["id"] = "security-001"
    near_copy["severity"] = "Critical"
    assert RFS.member_carries_sentinel(near_copy) is True


def test_member_carries_sentinel_false_for_ordinary_prose():
    assert RFS.member_carries_sentinel(
        {"id": "code-001", "severity": "Minor", "body": "Ordinary review prose."}
    ) is False


def test_member_carries_sentinel_false_for_prose_quoting_sentinel():
    # axis: embedded sentinel in real prose is not a placeholder-echo field value
    sentinel = RFS.EXAMPLE_SENTINEL
    assert RFS.member_carries_sentinel(
        {
            "severity": "Important",
            "title": "quoted example in body",
            "body": "context:\n" + sentinel + " appears inside prose",
        }
    ) is False


def test_substance_key_synonym_targets_are_canonical():
    # axis: every synonym maps to a declared canonical member key
    canonical = set(RFS.CANONICAL_MEMBER_KEYS)
    for synonym, target in RFS.SUBSTANCE_KEY_SYNONYMS.items():
        assert target in canonical, "%s -> %s" % (synonym, target)
    for synonym, target in RFS.STRUCTURAL_KEY_SYNONYMS.items():
        assert target in canonical, "%s -> %s" % (synonym, target)
    substance_and_structural = set(RFS.SUBSTANCE_KEY_SYNONYMS) | set(RFS.STRUCTURAL_KEY_SYNONYMS)
    assert substance_and_structural.isdisjoint(canonical)


@pytest.mark.parametrize(
    "member,expected",
    [
        ({"summary": "Title via summary"}, True),
        ({"message": "Body via message key"}, True),
        ({"description": "Body via description key"}, True),
        (
            {
                "severity": "Minor",
                "part": "src/a.py",
                "defect": "real defect prose",
                "change": "apply the fix",
            },
            True,
        ),
        ({"file": "a.py", "line": 3}, False),
        ({"severity": "Minor", "body": "   "}, False),
        ({"defect": "real prose"}, False),
        ({"severity": "Bogus", "defect": "real prose"}, False),
        ("not-a-dict", False),
    ],
    ids=[
        "specimen-summary",
        "specimen-message",
        "specimen-description",
        "specimen-pr1143-brief-check",
        "structural-only",
        "trivial-body",
        "censused-without-severity",
        "off-scale-severity-with-censused",
        "non-dict",
    ],
)
def test_member_is_engaged_table(member, expected):
    assert RFS.member_is_engaged(member) is expected


def test_normalize_member_adds_canonical_for_synonym():
    member = {"message": "Body text"}
    out = RFS.normalize_member(member)
    assert out["message"] == "Body text"
    assert out["body"] == "Body text"


def test_normalize_member_does_not_overwrite_existing_target():
    # axis: additive normalization never overwrites an existing canonical key
    member = {"message": "from message", "body": "canonical body"}
    out = RFS.normalize_member(member)
    assert out["body"] == "canonical body"
    assert out["message"] == "from message"


def test_normalize_member_preserves_unknown_keys():
    member = {"custom": "value", "message": "text"}
    out = RFS.normalize_member(member)
    assert out["custom"] == "value"


def test_normalize_member_does_not_mutate_input():
    member = {"message": "text"}
    original = dict(member)
    RFS.normalize_member(member)
    assert member == original


def test_example_findings_object_member_keys_are_canonical():
    member = RFS.example_findings_object()["findings"][0]
    assert set(member.keys()) == set(RFS.CANONICAL_MEMBER_KEYS)


def test_example_findings_object_is_engaged_and_values_in_set():
    member = RFS.example_findings_object()["findings"][0]
    assert RFS.member_is_engaged(member) is True
    placeholders = RFS.example_member_values()
    for value in member.values():
        if isinstance(value, str):
            assert value in placeholders


def test_example_prompt_block_contains_json_and_format_only_sentence():
    block = RFS.example_prompt_block()
    assert "Format only" in block
    assert "echoed example grades hollow" in block
    assert json.dumps(RFS.example_findings_object(), indent=2, sort_keys=True) in block
