# plugins/superheroes/lib/tests/test_ship_gate.py
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
    r = ship_gate.decide(_prov(), CLEAN, HEAD)
    assert r["action"] == "proceed" and "build + review" in r["reason"]


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
    prov = ship_gate.read_provenance(p)
    r = ship_gate.decide(prov, CLEAN, HEAD)
    assert r["action"] == "proceed"
    # purity: a re-read of the same durable evidence yields the identical decision
    assert ship_gate.decide(ship_gate.read_provenance(p), CLEAN, HEAD) == r


def test_gate_when_head_is_none():
    # a failed `git rev-parse HEAD` (head=None) must never proceed, even with a real covers
    r = ship_gate.decide(_prov(covers=HEAD), CLEAN, None)
    assert r["action"] == "gate" and "stale" in r["reason"]


def test_gate_when_review_is_non_dict():
    prov = {"build": BUILD, "review": "oops"}
    r = ship_gate.decide(prov, CLEAN, HEAD)
    assert r["action"] == "gate" and "stale" in r["reason"]


def test_read_provenance_nonobject_json_raises(tmp_path):
    p = tmp_path / "provenance.json"
    p.write_text("[1, 2, 3]")
    with pytest.raises(ship_gate.ProvenanceError):
        ship_gate.read_provenance(str(p))


def test_write_build_aborts_on_garbled_not_clobber(tmp_path):
    p = tmp_path / "provenance.json"
    p.write_text("{garbled")
    with pytest.raises(ship_gate.ProvenanceError):
        ship_gate.write_build(str(p), engine="subagent-driven-development", head=HEAD)
    assert p.read_text() == "{garbled"  # unchanged — never clobbered


# --- Task 8: a denied substantive build step is incomplete evidence -> gate (UFR-6/UFR-8) ---

def _clean_review(head):
    return {"action": ship_gate._TERMINAL}


def test_denied_build_step_gates_even_with_build_present():
    prov = {"build": {"engine": "claude", "head": "abc"},
            "review": {"covers": "abc"},
            "buildDenials": [{"step": "task-3", "command": "python3 -c x"}]}
    out = ship_gate.decide(prov, _clean_review("abc"), "abc")
    assert out["action"] == "gate"
    assert "incomplete" in out["reason"] or "denied" in out["reason"]


def test_clean_build_still_proceeds():
    prov = {"build": {"engine": "claude", "head": "abc"}, "review": {"covers": "abc"}}
    out = ship_gate.decide(prov, _clean_review("abc"), "abc")
    assert out["action"] == "proceed"


def test_record_build_denial_appends_not_clobber(tmp_path):
    p = str(tmp_path / "provenance.json")
    ship_gate.write_build(p, engine="subagent-driven-development", head=HEAD)
    ship_gate.record_build_denial(p, step="task-3", command="python3 -c x")
    ship_gate.record_build_denial(p, step="task-4", command="node -e y")
    prov = ship_gate.read_provenance(p)
    assert prov["build"]["head"] == HEAD  # build evidence preserved
    denials = prov["buildDenials"]
    assert [d["step"] for d in denials] == ["task-3", "task-4"]
    assert denials[0]["command"] == "python3 -c x"


def test_record_build_denial_aborts_on_garbled_not_clobber(tmp_path):
    p = tmp_path / "provenance.json"
    p.write_text("{garbled")
    with pytest.raises(ship_gate.ProvenanceError):
        ship_gate.record_build_denial(str(p), step="task-3", command="python3 -c x")
    assert p.read_text() == "{garbled"  # unchanged — never clobbered


# --- premortem-001: the journal is a SECOND build-denial carrier; either carrier gates ---

def test_journal_only_denial_still_gates():
    # provenance carries NO buildDenials (its write was lost), but the journal recorded the
    # `build:` denial first — the ship gate must still GATE off the journal carrier alone.
    prov = {"build": {"engine": "claude", "head": "abc"}, "review": {"covers": "abc"}}
    jdenials = [{"step": "build:9", "command": "run the migration"}]
    out = ship_gate.decide(prov, _clean_review("abc"), "abc", journal_denials=jdenials)
    assert out["action"] == "gate"
    assert "incomplete" in out["reason"] or "denied" in out["reason"]


def test_provenance_denial_gates_even_when_journal_unreadable():
    # journal unreadable -> journal_build_denials returned [] (fail-safe toward provenance-only);
    # the provenance carrier alone still GATEs.
    prov = {"build": {"engine": "claude", "head": "abc"}, "review": {"covers": "abc"},
            "buildDenials": [{"step": "build:9", "command": "python3 -c x"}]}
    out = ship_gate.decide(prov, _clean_review("abc"), "abc", journal_denials=[])
    assert out["action"] == "gate"


def test_both_carriers_empty_proceeds():
    prov = {"build": {"engine": "claude", "head": "abc"}, "review": {"covers": "abc"}}
    out = ship_gate.decide(prov, _clean_review("abc"), "abc", journal_denials=[])
    assert out["action"] == "proceed"


def test_journal_build_denials_filters_to_build_steps(tmp_path):
    import journal
    p = str(tmp_path / "events.jsonl")
    journal.append(p, "permission_denied", step="build:9", detail="run the migration")
    journal.append(p, "permission_denied", step="review:probe", detail="a reviewer probe")  # not build:
    journal.append(p, "allowance_fired", payload={"reason": "routine"})                     # not a denial
    got = ship_gate.journal_build_denials(p)
    assert got == [{"step": "build:9", "command": "run the migration"}]


def test_journal_build_denials_absent_file_is_empty():
    # a missing events file (or any read error) swallows to [] -> fold only ever ADDs, never clears.
    assert ship_gate.journal_build_denials("/nonexistent/events.jsonl") == []
