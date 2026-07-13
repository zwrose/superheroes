import importlib.util, json, os

LIB = os.path.join(os.path.dirname(__file__), "..")


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_convergence_counts_blocking_and_routed_per_round(tmp_path):
    rc = _load("review_convergence")
    records = str(tmp_path / "round-records.json")
    # round-records.json is a bare list on disk (review_memory.load_records_state's shape) — the
    # same shape Tasks 13/17's fixtures use.
    open(records, "w").write(json.dumps([
        {"round": 1, "findings": [
            {"severity": "Critical", "title": "a"}, {"severity": "Minor", "title": "b"}]},
        {"round": 2, "findings": [{"severity": "Minor", "title": "c"}]},
    ]))
    out = rc.compose_convergence(records, "plan", "passed")
    assert out["doc"] == "plan" and out["roundsUsed"] == 2 and out["outcome"] == "passed"
    assert out["perRound"] == [
        {"round": 1, "blocking": 1, "routedForward": 1},
        {"round": 2, "blocking": 0, "routedForward": 1}]


def test_convergence_unreadable_records_fails_soft(tmp_path):
    rc = _load("review_convergence")
    out = rc.compose_convergence(str(tmp_path / "missing.json"), "plan", "parked")
    assert out == {"doc": "plan", "outcome": "parked", "roundsUsed": 0, "perRound": []}
