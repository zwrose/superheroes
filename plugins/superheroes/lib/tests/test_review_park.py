import importlib.util, json, os

LIB = os.path.join(os.path.dirname(__file__), "..")


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


def test_compose_decision_list_from_open_blockers(tmp_path):
    rp = _load("review_park")
    records = str(tmp_path / "round-records.json")
    # round-records.json is a bare list on disk (review_memory.load_records_state fails closed
    # to "corrupt" on anything else) — the same shape Tasks 13/17's fixtures use.
    open(records, "w").write(json.dumps([
        {"round": 3, "findings": [
            {"file": "plan.md", "title": "unauth write path", "severity": "Critical",
             "docSection": "Architecture", "summary": "the write path skips auth"},
            {"file": "plan.md", "title": "nit", "severity": "Minor", "docSection": "Goals"},
        ]}]))
    out = rp.compose_park(records, 3, "plan", "open blocking finding at the doc-review round cap")
    assert out["ok"]
    assert out["payload"]["reason"].startswith("open blocking finding")
    dl = out["payload"]["decisions"]
    assert len(dl) == 1                      # only the blocking finding becomes a decision
    d = dl[0]
    assert d["docSection"] == "Architecture"
    assert "accept" in d["moves"][0].lower() or "fix" in d["moves"][0].lower()
    assert len(d["moves"]) == 2              # the two owner moves (direct-a-fix, accept-through-gate)


def test_unreadable_records_still_parks_with_note(tmp_path):
    rp = _load("review_park")
    out = rp.compose_park(str(tmp_path / "missing.json"), 3, "plan", "cap reached")
    assert out["ok"] and out["payload"]["decisions"] == []
    assert "could not" in out["payload"]["note"].lower()


def test_decision_text_is_scrubbed_before_it_reaches_the_payload(tmp_path):
    # journal.append writes `payload` as-is (no scrub) — compose_park is the only place left
    # that can protect the `parked` event from a finding whose title/summary round-tripped a
    # secret shape. Bearer-token shape matches an existing pr_comment._SCRUB_PATTERNS pattern.
    rp = _load("review_park")
    records = str(tmp_path / "round-records.json")
    open(records, "w").write(json.dumps([
        {"round": 3, "findings": [
            {"file": "plan.md", "title": "rotate the leaked token: Bearer abcdef0123456789",
             "severity": "Critical", "docSection": "Security"},
        ]}]))
    out = rp.compose_park(records, 3, "plan", "open blocking finding at the doc-review round cap")
    d = out["payload"]["decisions"][0]
    assert "abcdef0123456789" not in d["statement"]
    assert "abcdef0123456789" not in d["accepting_means"]
    assert "[REDACTED]" in d["statement"]
