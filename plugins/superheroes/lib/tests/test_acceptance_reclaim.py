# plugins/superheroes/lib/tests/test_acceptance_reclaim.py
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import acceptance_reclaim as rc


def test_no_in_flight_state_proceeds():
    r = rc.decide({"in_flight": False, "stamp": None, "has_record": False}, liveness="dead")
    assert r["action"] == "proceed"


def test_confirmed_alive_refuses_in_flight():
    r = rc.decide({"in_flight": True, "stamp": "s", "has_record": True}, liveness="alive")
    assert r["action"] == "refuse"


def test_confirmed_dead_reclaims_and_writes_orphan_record_when_none():
    r = rc.decide({"in_flight": True, "stamp": "s", "has_record": False}, liveness="dead")
    assert r["action"] == "reclaim"
    assert r["write_orphan_record"] is True


def test_confirmed_dead_with_existing_record_does_not_write_second():
    r = rc.decide({"in_flight": True, "stamp": "s", "has_record": True}, liveness="dead")
    assert r["action"] == "reclaim"
    assert r["write_orphan_record"] is False


def test_unconfirmable_liveness_refuses_like_ufr4():
    r = rc.decide({"in_flight": True, "stamp": "s", "has_record": True}, liveness="unconfirmable")
    assert r["action"] == "refuse"
