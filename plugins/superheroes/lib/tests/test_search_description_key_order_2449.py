"""searchDescription key order is `examples, kind, looksLike` everywhere it is defined (#2449).

Codex streams whitespace at the forced `looksLike` -> `examples` step under --output-schema (#2441);
listing the properties as `examples, kind, looksLike` removes the stall. Key order means nothing to a
validator, so the second half of this file proves the reordered schema accepts and rejects exactly
what the old order did.
"""
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


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ERC = _load("engine_result_channel")
RFS = _load("review_findings_schema")

NEW_ORDER = ["examples", "kind", "looksLike"]
OLD_ORDER = ["kind", "looksLike", "examples"]
SCHEMA_JSON_PATH = os.path.join(_LIB, "schemas", "review-findings.schema.json")


def _json_file():
    with open(SCHEMA_JSON_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _json_site():
    return _json_file()["properties"]["findings"]["items"]["properties"]["searchDescription"]


def _fallback_site():
    return RFS._FALLBACK_FINDING_PROPERTY_SCHEMAS["searchDescription"]


def _composed_branch(kind):
    assert ERC.review_findings_schema.SCHEMA_READ_USED_FALLBACK is False
    return ERC.declared_schema("codex", "review", kind)["properties"]["result"]


def _composed_findings_site():
    items = _composed_branch("findings")["properties"]["findings"]["items"]
    return items["properties"]["searchDescription"]


def _composed_ruling_site():
    new_issues = _composed_branch("ruling")["properties"]["newIssues"]
    assert "array" in new_issues["type"] and "null" in new_issues["type"]
    return new_issues["items"]["properties"]["searchDescription"]


SITES = {
    "review-findings.schema.json findings.items": _json_site,
    "review_findings_schema._FALLBACK_FINDING_PROPERTY_SCHEMAS": _fallback_site,
    "composed codex findings result.findings.items": _composed_findings_site,
    "composed codex ruling result.newIssues.items": _composed_ruling_site,
}


# axis: the key order of searchDescription's properties and required list at every site that defines
# or composes it (JSON file, fallback literal, both composed codex schemas) is examples, kind, looksLike.
@pytest.mark.parametrize("site", sorted(SITES))
def test_search_description_key_order_pinned(site):
    node = SITES[site]()
    assert list(node["properties"]) == NEW_ORDER, "%s: properties order %r" % (site, list(node["properties"]))
    assert list(node["required"]) == NEW_ORDER, "%s: required order %r" % (site, list(node["required"]))


# axis: the fallback literal and the JSON file agree on searchDescription including key order.
def test_fallback_literal_matches_json_file_including_order():
    from_json = _json_site()
    fallback = _fallback_site()
    assert list(fallback["properties"]) == list(from_json["properties"])
    assert list(fallback["required"]) == list(from_json["required"])
    assert fallback["type"] == from_json["type"]
    assert fallback["additionalProperties"] == from_json["additionalProperties"]


# ----- sibling: the reordered schema accepts exactly what the old order accepted -----

def _is_search_description(node):
    props = node.get("properties")
    return isinstance(props, dict) and set(props) == set(OLD_ORDER)


def _rewrite_to_old_order(node, counter):
    """In place: put every searchDescription object back to kind, looksLike, examples."""
    if isinstance(node, dict):
        for value in node.values():
            _rewrite_to_old_order(value, counter)
        if _is_search_description(node):
            node["properties"] = {key: node["properties"][key] for key in OLD_ORDER}
            node["required"] = list(OLD_ORDER)
            counter.append(1)
    elif isinstance(node, list):
        for value in node:
            _rewrite_to_old_order(value, counter)


def _old_order_copy(schema):
    out = copy.deepcopy(schema)
    counter = []
    _rewrite_to_old_order(out, counter)
    assert len(counter) == 1, "expected exactly one searchDescription to rewrite, rewrote %d" % len(counter)
    return out


def _sample(schema):
    """A minimal value satisfying schema, preferring non-null."""
    if "enum" in schema:
        non_null = [v for v in schema["enum"] if v is not None]
        return non_null[0] if non_null else None
    if "anyOf" in schema:
        return _sample(schema["anyOf"][0])
    kind = schema.get("type")
    if isinstance(kind, list):
        non_null = [t for t in kind if t != "null"]
        kind = non_null[0] if non_null else "null"
    if kind == "string":
        return "x"
    if kind in ("integer", "number"):
        return 0
    if kind == "boolean":
        return True
    if kind == "array":
        return []
    if kind == "object":
        props = schema.get("properties", {})
        return {key: _sample(props[key]) for key in schema.get("required", [])}
    return None


def _is_nullable(schema):
    kind = schema.get("type")
    return kind == "null" or (isinstance(kind, list) and "null" in kind)


def _base_finding(finding_schema):
    finding = _sample(finding_schema)
    finding["kindOfMistake"] = None
    finding["searchDescription"] = None
    return finding


def _branch_answer(branch, kind, finding):
    """A valid answer for the branch: every required key present, inactive payload keys null."""
    result = {}
    for key in branch["required"]:
        prop = branch["properties"][key]
        if key == "resultKind":
            result[key] = kind
        elif key == "findings" and kind == "findings":
            result[key] = [finding]
        elif key == "newIssues" and kind == "ruling":
            result[key] = [finding]
        elif _is_nullable(prop):
            result[key] = None
        else:
            result[key] = _sample(prop)
    return {"result": result}


FULL = {"kind": "k", "looksLike": "l", "examples": ["e"]}


def _full_new_order():
    return {key: FULL[key] for key in NEW_ORDER}


def _both_filled(finding):
    finding["kindOfMistake"] = {"kind": "k", "places": [{"file": "a.py", "line": 3}]}
    finding["searchDescription"] = dict(FULL)


def _set_sd(value):
    def apply(finding):
        finding["searchDescription"] = value
    return apply


def _drop_examples(finding):
    finding["searchDescription"] = {"kind": "k", "looksLike": "l"}


def _extra_key(finding):
    finding["searchDescription"] = dict(FULL, extra="nope")


def _examples_string(finding):
    finding["searchDescription"] = dict(FULL, examples="e")


# (row id, mutate the finding, expected acceptance, which composed schema carries the answer)
ROWS = [
    ("full-old-key-order", _set_sd(dict(FULL)), True, "findings"),
    ("full-new-key-order", _set_sd(_full_new_order()), True, "findings"),
    ("null", _set_sd(None), True, "findings"),
    ("empty-examples", _set_sd(dict(FULL, examples=[])), True, "findings"),
    ("both-kind-of-mistake-and-search-description", _both_filled, True, "findings"),
    ("ruling-new-issues-holds-finding", _set_sd(dict(FULL)), True, "ruling"),
    ("missing-examples", _drop_examples, False, "findings"),
    ("extra-key", _extra_key, False, "findings"),
    ("examples-is-string", _examples_string, False, "findings"),
]


def _finding_schema_of(kind):
    branch = _composed_branch(kind)
    if kind == "findings":
        return branch["properties"]["findings"]["items"]
    return branch["properties"]["newIssues"]["items"]


# axis: the composed codex schemas (findings and ruling kinds) accept and reject the same answers
# after the reorder as the old key order did, row by row, with the expected verdict pinned per row.
@pytest.mark.parametrize("row_id,mutate,expected,kind", ROWS, ids=[r[0] for r in ROWS])
def test_reordered_composed_schema_agrees_with_old_order(row_id, mutate, expected, kind):
    new_schema = ERC.declared_schema("codex", "review", kind)
    old_schema = _old_order_copy(new_schema)
    old_sd = old_schema["properties"]["result"]
    old_sd = (old_sd["properties"]["findings"]["items"] if kind == "findings"
              else old_sd["properties"]["newIssues"]["items"])["properties"]["searchDescription"]
    assert list(old_sd["properties"]) == OLD_ORDER and list(old_sd["required"]) == OLD_ORDER
    branch = new_schema["properties"]["result"]
    finding = _base_finding(_finding_schema_of(kind))
    mutate(finding)
    answer = _branch_answer(branch, kind, finding)
    new_ok, new_reason = ERC.validate(new_schema, answer)
    old_ok, old_reason = ERC.validate(old_schema, answer)
    assert new_ok == old_ok, "%s: new=%r (%s) old=%r (%s)" % (row_id, new_ok, new_reason, old_ok, old_reason)
    assert new_ok is expected, "%s: expected %r, got %r (%s)" % (row_id, expected, new_ok, new_reason)


# axis: the same agreement holds under the independent jsonschema library, against the JSON file's
# findings.items schema, so the reorder is not merely agreed on by our own validator.
@pytest.mark.parametrize("row_id,mutate,expected,kind", ROWS, ids=[r[0] for r in ROWS])
def test_reordered_json_file_agrees_with_old_order_under_jsonschema(row_id, mutate, expected, kind):
    jsonschema = pytest.importorskip("jsonschema")
    new_items = _json_file()["properties"]["findings"]["items"]
    old_items = _old_order_copy(new_items)
    finding = _base_finding(new_items)
    mutate(finding)
    new_ok = jsonschema.Draft7Validator(new_items).is_valid(finding)
    old_ok = jsonschema.Draft7Validator(old_items).is_valid(finding)
    assert new_ok == old_ok, "%s: new=%r old=%r" % (row_id, new_ok, old_ok)
    assert new_ok is expected, "%s: expected %r, got %r" % (row_id, expected, new_ok)
