"""Tests for session_mode.resolve — review-session mode SSOT (#1151)."""
import pytest

import session_mode as sm


def _assert_resolved(result, mode, evidence):
    assert result == {
        "mode": mode,
        "evidence": evidence,
        "resolved": True,
        "disclosure": None,
    }


def _assert_unresolved(result, disclosure_substr=None):
    assert result["mode"] == sm.MODE_PR
    assert result["evidence"] == sm.EVIDENCE_UNRESOLVED
    assert result["resolved"] is False
    assert isinstance(result["disclosure"], str)
    assert result["disclosure"]
    if disclosure_substr is not None:
        assert disclosure_substr in result["disclosure"]


def test_resolve_meta_mode_pr():
    _assert_resolved(sm.resolve({"mode": "pr"}, {}), "pr", sm.EVIDENCE_SESSION_META)


def test_resolve_meta_mode_branch():
    _assert_resolved(
        sm.resolve({"mode": "branch"}, {}), "branch", sm.EVIDENCE_SESSION_META,
    )


def test_resolve_config_mode_when_meta_empty():
    _assert_resolved(
        sm.resolve({}, {"mode": "branch"}), "branch", sm.EVIDENCE_DRIVER_CONFIG,
    )


def test_resolve_unresolved_when_both_empty():
    _assert_unresolved(sm.resolve({}, {}), "not set")


def test_resolve_invalid_meta_does_not_fall_through_to_config():
    _assert_unresolved(
        sm.resolve({"mode": "bogus"}, {"mode": "branch"}),
        "session metadata",
    )


@pytest.mark.parametrize("meta", [{"mode": ""}, {"mode": None}])
def test_resolve_present_but_invalid_empty_meta(meta):
    _assert_unresolved(sm.resolve(meta, {"mode": "branch"}), "session metadata")


@pytest.mark.parametrize("meta", [{"mode": 123}, {"mode": ["pr"]}])
def test_resolve_non_string_meta_mode(meta):
    _assert_unresolved(sm.resolve(meta, {}))


def test_resolve_none_inputs():
    _assert_unresolved(sm.resolve(None, None))


def test_resolve_non_dict_inputs():
    _assert_unresolved(sm.resolve("notadict", 42))


def test_resolve_wrong_case_meta_mode():
    _assert_unresolved(sm.resolve({"mode": "PR"}, {"mode": "branch"}))


_MALFORMED_INPUTS = [
    (None, None),
    ("notadict", 42),
    ({"mode": 123}, {}),
    ({"mode": ["pr"]}, {}),
    ({"mode": ""}, {}),
    ({"mode": None}, {}),
    ({"mode": "bogus"}, {}),
    ({"mode": "PR"}, {}),
    ({}, {}),
]


@pytest.mark.parametrize("meta,config", _MALFORMED_INPUTS)
def test_resolve_never_raises(meta, config):
    sm.resolve(meta, config)


def test_resolve_purity_equal_but_not_identical():
    first = sm.resolve({"mode": "pr"}, {})
    second = sm.resolve({"mode": "pr"}, {})
    assert first == second
    assert first is not second


def test_resolve_purity_mutation_does_not_affect_next_call():
    result = sm.resolve({}, {})
    result["mode"] = "branch"
    result["resolved"] = True
    next_result = sm.resolve({}, {})
    _assert_unresolved(next_result, "not set")


def test_evidence_line_resolved_from_meta():
    result = sm.resolve({"mode": "pr"}, {})
    assert sm.evidence_line(result) == "Review session mode pr (from session metadata)."


def test_evidence_line_resolved_from_config():
    result = sm.resolve({}, {"mode": "branch"})
    assert (
        sm.evidence_line(result)
        == "Review session mode branch (from driver configuration)."
    )


def test_evidence_line_unresolved_returns_disclosure():
    result = sm.resolve({}, {})
    assert sm.evidence_line(result) == result["disclosure"]
