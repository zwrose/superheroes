"""The locked-artifact JSON schemas are well-formed, and accept/reject the right shapes.

Schema-validation tests use `jsonschema` (installed in CI); they `importorskip` so a
local run without it still passes the well-formedness checks.
"""
import glob
import json
import os

import pytest

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
    "define-doc.schema.json": {
        "superheroes": "doc", "schemaVersion": 1, "docType": "tasks",
        "workItem": "add-toggle-abc123", "issue": 42,
        "parent": {"workItem": "add-toggle-abc123", "docType": "plan"},
        "size": "medium", "status": "approved", "gates": {"review": "passed"},
        "producedBy": "define@0.1.0", "created": "2026-06-14", "updated": "2026-06-14"},
    "checkpoint.schema.json": {
        "schemaVersion": 1, "workItem": "add-toggle-abc123", "issue": 42, "size": "medium",
        "phase": "tasks", "gates": {"spec": "passed", "plan": "passed", "tasks": "pending"},
        "patternsPin": "0123456789abcdef", "branch": "superheroes/add-toggle-abc123-0123456789abcdef",
        "lockGeneration": 7, "pr": {"number": 42, "url": "https://example/pr/42"},
        "lastGoodStep": "step-3", "updatedAt": "2026-06-14T00:00:00Z"},
    "queue.schema.json": {
        "schemaVersion": 1,
        "items": [{"workItem": "add-toggle-abc123", "issue": 42, "state": "queued", "order": 0}]},
    "registry.schema.json": {
        "schemaVersion": 1, "storageMode": "global", "remoteKey": "deadbeefdeadbeef",
        "createdAt": "2026-06-14"},
}

INVALID = {
    "define-doc.schema.json": dict(VALID["define-doc.schema.json"], docType="design"),  # "design" is not a docType
    "checkpoint.schema.json": dict(VALID["checkpoint.schema.json"], phase="unknown"),
    "queue.schema.json": {"schemaVersion": 1, "items": [{"workItem": "x", "state": "queued", "order": 0}]},  # missing issue
    "registry.schema.json": dict(VALID["registry.schema.json"], storageMode="hybrid"),  # not a mode
}


def test_valid_samples_validate():
    jsonschema = pytest.importorskip("jsonschema")
    for name, sample in VALID.items():
        jsonschema.validate(sample, _load(name))


def test_invalid_samples_are_rejected():
    jsonschema = pytest.importorskip("jsonschema")
    for name, sample in INVALID.items():
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(sample, _load(name))
