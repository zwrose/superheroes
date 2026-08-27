"""Unit tests for owner-gate fold policyApplied source provenance branching."""
import round_driver as RD

_PHASE = "present-judgment"

_WELL_FORMED_PROVENANCE = {
    "ruledBy": "owner",
    "ruledAt": "2026-08-26T00:00:00Z",
    "records": ["gate-ruling.json"],
}

_WELL_FORMED_ARTIFACT = {
    "dispositions": [],
    "_provenance": _WELL_FORMED_PROVENANCE,
}


def _record(artifact):
    return RD._owner_supplied_applied_record(_PHASE, artifact)


def _expected_sha256(artifact):
    return RD._sha256(RD._canonical(artifact))


def test_well_formed_provenance_yields_owner_supplied():
    # axis: well-formed _provenance block → owner-supplied source constant
    record = _record(_WELL_FORMED_ARTIFACT)
    assert record["source"] is RD.POLICY_APPLIED_SOURCE_OWNER_SUPPLIED


def test_malformed_provenance_shapes_yield_owner_unattributed():
    # axis: enumerated malformed _provenance shapes → owner-unattributed source constant
    _VALID_TAIL = {"ruledAt": "2026-08-26T00:00:00Z", "records": ["gate-ruling.json"]}
    cases = [
        ("provenance_absent", {"dispositions": []}),
        ("provenance_is_list", {"_provenance": []}),
        ("provenance_is_string", {"_provenance": "x"}),
        ("provenance_is_number", {"_provenance": 1}),
        ("provenance_is_null", {"_provenance": None}),
        ("provenance_is_bool", {"_provenance": True}),
        ("ruledBy_missing", {"_provenance": dict(_VALID_TAIL)}),
        ("ruledBy_not_string", {"_provenance": {"ruledBy": 1, **_VALID_TAIL}}),
        ("ruledBy_empty", {"_provenance": {"ruledBy": "", **_VALID_TAIL}}),
        ("ruledBy_whitespace", {"_provenance": {"ruledBy": "   ", **_VALID_TAIL}}),
        ("ruledAt_missing", {"_provenance": {"ruledBy": "owner", "records": ["gate-ruling.json"]}}),
        ("ruledAt_not_string", {"_provenance": {"ruledBy": "owner", "ruledAt": 1, "records": ["x"]}}),
        ("ruledAt_empty", {"_provenance": {"ruledBy": "owner", "ruledAt": "", "records": ["x"]}}),
        ("ruledAt_whitespace", {"_provenance": {"ruledBy": "owner", "ruledAt": "  ", "records": ["x"]}}),
        ("records_missing", {"_provenance": {"ruledBy": "owner", "ruledAt": "2026-08-26T00:00:00Z"}}),
        ("records_not_list", {"_provenance": {"ruledBy": "owner", "ruledAt": "2026-08-26T00:00:00Z", "records": "x"}}),
        ("records_empty_list", {"_provenance": {"ruledBy": "owner", "ruledAt": "2026-08-26T00:00:00Z", "records": []}}),
        ("records_non_string_element", {"_provenance": {"ruledBy": "owner", "ruledAt": "2026-08-26T00:00:00Z", "records": [1]}}),
        ("records_empty_string_element", {"_provenance": {"ruledBy": "owner", "ruledAt": "2026-08-26T00:00:00Z", "records": [""]}}),
        ("records_whitespace_string_element", {"_provenance": {"ruledBy": "owner", "ruledAt": "2026-08-26T00:00:00Z", "records": ["  "]}}),
        ("artifact_not_dict_none", None),
        ("artifact_not_dict_list", []),
        ("artifact_not_dict_string", "artifact"),
        ("artifact_not_dict_number", 1),
    ]
    assert len(cases) == 24
    for name, artifact in cases:
        record = _record(artifact)
        assert record["source"] is RD.POLICY_APPLIED_SOURCE_OWNER_UNATTRIBUTED, name


def test_field_preservation_both_branches():
    # axis: action, artifactSha256, layers, and matches preserved in both source branches
    well_formed = _record(_WELL_FORMED_ARTIFACT)
    assert well_formed["phase"] == _PHASE
    assert well_formed["action"] is _WELL_FORMED_ARTIFACT
    assert well_formed["artifactSha256"] == _expected_sha256(_WELL_FORMED_ARTIFACT)
    assert well_formed["layers"] == []
    assert well_formed["matches"] == []

    unattributed_artifact = {"dispositions": []}
    unattributed = _record(unattributed_artifact)
    assert unattributed["phase"] == _PHASE
    assert unattributed["action"] is unattributed_artifact
    assert unattributed["artifactSha256"] == _expected_sha256(unattributed_artifact)
    assert unattributed["layers"] == []
    assert unattributed["matches"] == []


def test_gate_policy_applied_record_unaffected():
    # axis: gate-policy source constant unchanged on calibration-resolved folds
    resolution = {"layers": [], "matches": [], "action": {"dispositions": []}}
    record = RD._policy_applied_record(_PHASE, resolution)
    assert record["source"] is RD.POLICY_APPLIED_SOURCE_GATE_POLICY


def test_well_formed_provenance_tolerates_unknown_extra_keys():
    # axis: unknown extra keys inside _provenance do not invalidate well-formed block
    artifact = {
        "dispositions": [],
        "_provenance": {**_WELL_FORMED_PROVENANCE, "extraField": "ignored"},
    }
    record = _record(artifact)
    assert record["source"] is RD.POLICY_APPLIED_SOURCE_OWNER_SUPPLIED
