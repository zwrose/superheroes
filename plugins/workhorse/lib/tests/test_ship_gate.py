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


def test_write_build_then_set_review_covers_preserves_build(tmp_path):
    p = str(tmp_path / "provenance.json")
    ship_gate.write_build(p, engine="subagent-driven-development", head=HEAD)
    ship_gate.set_review_covers(p, HEAD)
    prov = ship_gate.read_provenance(p)
    assert prov["build"]["head"] == HEAD and prov["review"]["covers"] == HEAD


def test_read_provenance_absent_is_empty(tmp_path):
    assert ship_gate.read_provenance(str(tmp_path / "nope.json")) == {}


def test_read_provenance_garbled_raises(tmp_path):
    p = tmp_path / "provenance.json"
    p.write_text("{not json")
    with pytest.raises(ship_gate.ProvenanceError):
        ship_gate.read_provenance(str(p))


def test_set_review_covers_aborts_on_garbled_not_clobber(tmp_path):
    p = tmp_path / "provenance.json"
    p.write_text("{garbled")
    with pytest.raises(ship_gate.ProvenanceError):
        ship_gate.set_review_covers(str(p), HEAD)
    assert p.read_text() == "{garbled"  # unchanged — never clobbered


def test_decide_is_deterministic_round_trip(tmp_path):
    p = str(tmp_path / "provenance.json")
    ship_gate.write_build(p, engine="subagent-driven-development", head=HEAD)
    ship_gate.set_review_covers(p, HEAD)
    prov1 = ship_gate.read_provenance(p)
    prov2 = ship_gate.read_provenance(p)
    assert ship_gate.decide(prov1, CLEAN, HEAD) == ship_gate.decide(prov2, CLEAN, HEAD)
    assert ship_gate.decide(prov1, CLEAN, HEAD)["action"] == "proceed"
