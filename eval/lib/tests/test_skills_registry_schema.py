import json, os
import jsonschema

SCHEMA = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "schemas", "skills-registry.schema.json",
)

def _schema():
    with open(SCHEMA) as fh:
        return json.load(fh)

def test_schema_well_formed():
    s = _schema()
    assert s.get("$schema") and s.get("type") == "object" and "properties" in s

def test_accepts_valid_registry():
    jsonschema.validate(
        {"bodyCeilings": {"review-crew/review-code": 500},
         "requiredPhrases": {"review-crew/review-code": ["review", "pull request"]}},
        _schema(),
    )

def test_rejects_noninteger_ceiling():
    import pytest
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"bodyCeilings": {"x/y": "500"}, "requiredPhrases": {}}, _schema())
