"""Tests for pilot_probe vocabulary and classification."""
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.realpath(os.path.join(_HERE, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import pilot_probe  # noqa: E402


def test_classes_pairwise_disjoint():
    assert pilot_probe.LAPSE_REASONS.isdisjoint(pilot_probe.INFRASTRUCTURE_REASONS)
    assert pilot_probe.LAPSE_REASONS.isdisjoint(pilot_probe.IDENTITY_REASONS)
    assert pilot_probe.INFRASTRUCTURE_REASONS.isdisjoint(pilot_probe.IDENTITY_REASONS)


def test_classes_union_equals_all_probe_reasons():
    union = (
        pilot_probe.LAPSE_REASONS
        | pilot_probe.INFRASTRUCTURE_REASONS
        | pilot_probe.IDENTITY_REASONS
    )
    assert union == pilot_probe.ALL_PROBE_REASONS


def test_token_count():
    assert len(pilot_probe.ALL_PROBE_REASONS) == pilot_probe.EXPECTED_TOKEN_COUNT == 10


def test_routes_to_lapse_per_token():
    for reason in pilot_probe.ALL_PROBE_REASONS:
        expected = reason == pilot_probe.REASON_NO_SESSION
        assert pilot_probe.routes_to_lapse(reason) is expected, reason


def test_is_infrastructure_per_token():
    for reason in pilot_probe.ALL_PROBE_REASONS:
        expected = reason in pilot_probe.INFRASTRUCTURE_REASONS
        assert pilot_probe.is_infrastructure(reason) is expected, reason


def test_classify_per_token():
    expected_class = {
        pilot_probe.REASON_TRANSPORT_ERROR: "infrastructure",
        pilot_probe.REASON_UNEXPECTED_STATUS: "infrastructure",
        pilot_probe.REASON_INVALID_BODY: "infrastructure",
        pilot_probe.REASON_NO_SESSION: "lapse",
        pilot_probe.REASON_WRONG_IDENTITY: "identity",
        pilot_probe.REASON_DISABLED_ACCOUNT: "identity",
        pilot_probe.REASON_UNAUTHORIZED: "identity",
        pilot_probe.REASON_FORBIDDEN: "identity",
        pilot_probe.REASON_RATE_LIMITED: "infrastructure",
        pilot_probe.REASON_INFRASTRUCTURE_UNAVAILABLE: "infrastructure",
    }
    for reason in pilot_probe.ALL_PROBE_REASONS:
        assert pilot_probe.classify(reason) == expected_class[reason], reason


def test_classify_none_raises():
    with pytest.raises(ValueError, match="unknown probe reason"):
        pilot_probe.classify(None)


def test_classify_empty_string_raises():
    with pytest.raises(ValueError, match="unknown probe reason"):
        pilot_probe.classify("")


def test_classify_wrong_case_raises():
    with pytest.raises(ValueError, match="unknown probe reason"):
        pilot_probe.classify("NO-SESSION")


def test_classify_trailing_whitespace_raises():
    with pytest.raises(ValueError, match="unknown probe reason"):
        pilot_probe.classify("no-session ")


def test_routes_to_lapse_none_is_false():
    assert pilot_probe.routes_to_lapse(None) is False


def test_is_infrastructure_none_is_false():
    assert pilot_probe.is_infrastructure(None) is False


def test_classify_substring_raises():
    with pytest.raises(ValueError, match="unknown probe reason"):
        pilot_probe.classify("session")
