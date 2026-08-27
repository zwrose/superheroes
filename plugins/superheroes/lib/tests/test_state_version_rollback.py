#!/usr/bin/env python3
"""#1185 — rollback refusal and hash-preserving load for STATE_SCHEMA_VERSION bump."""
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import round_driver as RD  # noqa: E402


def test_rollback_reader_refuses_schema_version_4(tmp_path, monkeypatch):
    """A v3-vintage reader (SUPPORTED_STATE_VERSIONS=(2, 3)) truthfully refuses schemaVersion 4."""
    monkeypatch.setattr(RD, "SUPPORTED_STATE_VERSIONS", (2, 3))
    d = str(tmp_path / "v4")
    os.makedirs(d)
    with open(os.path.join(d, RD.STATE_FILE), "w", encoding="utf-8") as fh:
        json.dump({"schemaVersion": 4, "rounds": {}}, fh)
    ok, reason = RD.load_state(d)
    assert ok is False
    assert isinstance(reason, str)
    assert "4" in reason
    assert "2" in reason and "3" in reason
    assert "not one of" in reason


@pytest.mark.parametrize("version", [2, 3, 4])
def test_load_state_accepts_supported_versions_unchanged(tmp_path, version):
    """The current reader accepts 2, 3, and 4 and returns schemaVersion exactly as persisted."""
    d = str(tmp_path / ("v%d" % version))
    os.makedirs(d)
    payload = {"schemaVersion": version, "rounds": {}, "round": 1}
    with open(os.path.join(d, RD.STATE_FILE), "w", encoding="utf-8") as fh:
        json.dump(payload, fh)
    ok, loaded = RD.load_state(d)
    assert ok is True
    assert loaded["schemaVersion"] == version
    assert set(loaded) == set(payload)
