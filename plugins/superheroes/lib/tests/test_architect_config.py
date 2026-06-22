# plugins/superheroes/lib/tests/test_architect_config.py
"""Conformance: the-architect doc-policy record (CONVENTIONS §2.3/§3.3/§4.2)."""
import importlib.util
import json
import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
_LIB = os.path.join(_REPO_ROOT, "plugins/superheroes/lib")


def _load(name):
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
    path = os.path.join(_LIB, name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


AC = _load("architect_config")


def test_read_policy_absent_is_none(tmp_path):
    # No project store / no doc-policy.json yet → None.
    assert AC.read_policy(str(tmp_path), root=str(tmp_path / "store")) is None


def test_write_then_read_roundtrips(tmp_path):
    store = str(tmp_path / "store")
    pol = {"location": "docs/specs", "visibility": AC.GITIGNORED, "confirmed": True}
    written = AC.write_policy(str(tmp_path), pol, root=store)
    assert written["location"] == "docs/specs"
    got = AC.read_policy(str(tmp_path), root=store)
    assert got["location"] == "docs/specs"
    assert got["visibility"] == AC.GITIGNORED
    assert got["confirmed"] is True


def test_read_policy_migrates_missing_fields(tmp_path):
    # A record from an earlier version (no `confirmed`, no schemaVersion) is tolerated and
    # filled forward on read; a subsequent read sees the current shape.
    store = str(tmp_path / "store")
    p = AC.policy_path(str(tmp_path), root=store)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as fh:
        json.dump({"location": "docs/superheroes", "visibility": "committed"}, fh)
    got = AC.read_policy(str(tmp_path), root=store)
    assert got["confirmed"] is False  # defaulted (treated as provisional)
    assert got["location"] == "docs/superheroes"


def test_read_policy_corrupt_is_none(tmp_path):
    store = str(tmp_path / "store")
    p = AC.policy_path(str(tmp_path), root=store)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as fh:
        fh.write("{ not json")
    assert AC.read_policy(str(tmp_path), root=store) is None


def test_read_policy_rejects_out_of_repo_location(tmp_path):
    # UFR-4: a recorded location that escapes the repo (absolute, or ../) is not honored —
    # it is normalized back to the safe default rather than letting a write land outside.
    store = str(tmp_path / "store")
    for bad in ("/etc/passwd-dir", "../../escape", "docs/../../x"):
        p = AC.policy_path(str(tmp_path), root=store)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as fh:
            json.dump({"location": bad, "visibility": "committed"}, fh)
        got = AC.read_policy(str(tmp_path), root=store)
        assert got["location"] == AC.DEFAULT_LOCATION, bad
