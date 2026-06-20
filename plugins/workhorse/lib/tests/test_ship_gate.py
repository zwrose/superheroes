# plugins/workhorse/lib/tests/test_ship_gate.py
import pytest
import ship_gate

HEAD = "abc1234"
CLEAN = {"action": "exit_clean"}
BUILD = {"engine": "subagent-driven-development", "head": HEAD}


def _prov(covers=HEAD, build=BUILD):
    p = {}
    if build is not None:
        p["build"] = build
    if covers is not None:
        p["review"] = {"covers": covers}
    return p


def test_proceed_when_build_and_fresh_clean_review():
    assert ship_gate.decide(_prov(), CLEAN, HEAD)["action"] == "proceed"


def test_gate_when_build_absent():
    r = ship_gate.decide(_prov(build=None), CLEAN, HEAD)
    assert r["action"] == "gate" and "build provenance absent" in r["reason"]


def test_gate_when_provenance_not_a_dict():
    r = ship_gate.decide("nope", CLEAN, HEAD)
    assert r["action"] == "gate" and "build provenance absent" in r["reason"]


def test_gate_when_review_missing_or_halt():
    r = ship_gate.decide(_prov(), {"action": "halt"}, HEAD)
    assert r["action"] == "gate" and "did not run" in r["reason"]


def test_gate_when_review_exit_skipped_names_skip():
    r = ship_gate.decide(_prov(), {"action": "exit_skipped"}, HEAD)
    assert r["action"] == "gate" and "skipped a blocking finding" in r["reason"]


def test_gate_when_review_non_terminal():
    r = ship_gate.decide(_prov(), {"action": "review"}, HEAD)
    assert r["action"] == "gate" and "did not terminate" in r["reason"]


def test_gate_when_review_result_not_a_dict():
    r = ship_gate.decide(_prov(), "halt", HEAD)
    assert r["action"] == "gate" and "did not run" in r["reason"]


def test_gate_when_covers_mismatch():
    r = ship_gate.decide(_prov(covers="oldsha"), CLEAN, HEAD)
    assert r["action"] == "gate" and "stale" in r["reason"]


def test_gate_when_covers_absent():
    r = ship_gate.decide(_prov(covers=None), CLEAN, HEAD)
    assert r["action"] == "gate" and "stale" in r["reason"]
