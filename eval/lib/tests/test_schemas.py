"""The locked-artifact JSON schemas are well-formed, and accept/reject the right shapes.

`jsonschema` is a hard test dependency (installed in CI). It is imported at module level
ON PURPOSE: if it's missing, this module errors at collection (pytest goes red) rather
than silently skipping the validation — a skipped schema gate is a false-green that hides
the `[live]` conformance check (eval/gate.md). Install it locally to run these tests.
"""
import glob
import json
import os
import re

import jsonschema
import pytest

import identifiers as ids

SCHEMA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "schemas")


def _schema_files():
    return sorted(glob.glob(os.path.join(SCHEMA_DIR, "*.schema.json")))


def _load(name):
    with open(os.path.join(SCHEMA_DIR, name)) as fh:
        return json.load(fh)


def test_schemas_present_and_well_formed():
    files = _schema_files()
    assert files, "no *.schema.json files found"
    for f in files:
        with open(f) as fh:
            s = json.load(fh)
        assert s.get("$schema"), f
        assert s.get("type") == "object", f
        assert "properties" in s, f


# A CONVENTIONS-conformant sample per schema, and a minimally-broken counterpart.
VALID = {
    "definition-doc.schema.json": {
        "superheroes": "doc", "schemaVersion": 1, "docType": "tasks",
        "workItem": "add-toggle-abc123", "issue": 42,
        "parent": {"workItem": "add-toggle-abc123", "docType": "plan"},
        "size": "medium", "status": "approved", "gates": {"review": "passed"},
        "producedBy": "the-architect@0.1.0", "created": "2026-06-14", "updated": "2026-06-14"},
    "checkpoint.schema.json": {
        "schemaVersion": 2, "workItem": "add-toggle-abc123", "issue": 42, "size": "medium",
        "phase": "tasks", "gates": {"spec": "passed", "plan": "passed", "tasks": "pending"},
        "patternsPin": "0123456789abcdef", "branch": "superheroes/add-toggle-abc123-0123456789abcdef",
        "lockGeneration": 7, "pr": {"number": 42, "url": "https://example/pr/42"},
        "lastGoodStep": 3, "lastGoodPhase": "tasks", "updatedAt": "2026-06-14T00:00:00Z"},
    "queue.schema.json": {
        "schemaVersion": 1,
        "items": [{"workItem": "add-toggle-abc123", "issue": 42, "state": "queued", "order": 0}]},
    "registry.schema.json": {
        "schemaVersion": 1, "storageMode": "global", "remoteKey": "deadbeefdeadbeef",
        "createdAt": "2026-06-14"},
}

INVALID = {
    "definition-doc.schema.json": dict(VALID["definition-doc.schema.json"], docType="design"),  # "design" is not a docType
    "checkpoint.schema.json": dict(VALID["checkpoint.schema.json"], phase="unknown"),
    "queue.schema.json": {"schemaVersion": 1, "items": [{"workItem": "add-toggle-abc123", "state": "queued", "order": 0}]},  # missing issue is the SOLE violation (workItem is a valid slug)
    "registry.schema.json": dict(VALID["registry.schema.json"], storageMode="hybrid"),  # not a mode
}


def test_valid_samples_validate():
    for name, sample in VALID.items():
        jsonschema.validate(sample, _load(name))


def test_invalid_samples_are_rejected():
    for name, sample in INVALID.items():
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(sample, _load(name))


def test_definition_doc_rejects_malformed_workitem():
    # The §6.1 slug pattern is the most spec-load-bearing schema rule; exercise it directly.
    bad = dict(VALID["definition-doc.schema.json"], workItem="add-toggle-zzzzzz")  # suffix not 6 hex
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, _load("definition-doc.schema.json"))


# The §6.1 work-item slug pattern is duplicated across every schema that carries a
# work-item (4 sites). These two tests are the anti-drift guard: all sites must use the
# SAME pattern, and that pattern must agree with what work_item_slug actually emits — so
# no schema can silently diverge from the canonical reference impl.
SLUG_PATTERN = r"^[a-z0-9][a-z0-9-]*-[0-9a-f]{6}$"


def _all_workitem_patterns():
    dd = _load("definition-doc.schema.json")
    cp = _load("checkpoint.schema.json")
    q = _load("queue.schema.json")
    return {
        "definition-doc.workItem": dd["properties"]["workItem"]["pattern"],
        "definition-doc.parent.workItem": dd["properties"]["parent"]["oneOf"][1]["properties"]["workItem"]["pattern"],
        "checkpoint.workItem": cp["properties"]["workItem"]["pattern"],
        "queue.items.workItem": q["properties"]["items"]["items"]["properties"]["workItem"]["pattern"],
    }


def test_workitem_pattern_consistent_across_schemas():
    pats = _all_workitem_patterns()
    assert all(p == SLUG_PATTERN for p in pats.values()), pats


def test_workitem_pattern_matches_reference_impl():
    # A real slug validates against the schema pattern; a raw title does not.
    assert re.fullmatch(SLUG_PATTERN, ids.work_item_slug("Some Example Title", "nonce"))
    assert not re.fullmatch(SLUG_PATTERN, "Some Example Title")
