import importlib.util, json, os

LIB = os.path.join(os.path.dirname(__file__), "..")


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_write_dedupes_and_names_plan_section(tmp_path):
    rh = _load("review_handoff")
    findings = [
        {"file": "plan.md", "title": "no named unit test", "severity": "Minor",
         "planSection": "Components & interfaces", "summary": "add a unit test for option A"},
        {"file": "plan.md", "title": "No Named Unit Test", "severity": "Minor",
         "planSection": "Components & interfaces", "summary": "dup, reworded case"},
        {"file": "plan.md", "title": "two literals for retry", "severity": "Minor",
         "planSection": "Data flow", "summary": "retry constant appears twice"},
    ]
    out = rh.write_handoff(str(tmp_path), "wi-1", findings)
    assert out["ok"]
    data = json.loads(open(os.path.join(str(tmp_path), "plan-handoff.json")).read())
    assert data["schemaVersion"] == 1 and data["workItem"] == "wi-1"
    assert data["counts"]["distinct"] == 2   # the two same-identity entries collapse
    assert {e["planSection"] for e in data["findings"]} == {"Components & interfaces", "Data flow"}


def test_read_absent_returns_structured_not_found(tmp_path):
    rh = _load("review_handoff")
    res = rh.read_handoff(str(tmp_path))
    assert res == {"ok": False, "reason": "absent"}


def test_read_roundtrips(tmp_path):
    rh = _load("review_handoff")
    rh.write_handoff(str(tmp_path), "wi-1", [
        {"file": "plan.md", "title": "x", "severity": "Minor", "planSection": "Goals"}])
    res = rh.read_handoff(str(tmp_path))
    assert res["ok"] and len(res["findings"]) == 1


def test_collect_nonblocking_from_round_records(tmp_path):
    rh = _load("review_handoff")
    records_path = tmp_path / "round-records.json"
    records_path.write_text(json.dumps([
        {"round": 1, "findings": [
            {"file": "plan.md", "title": "blocker", "severity": "Important"},
            {"file": "plan.md", "title": "minor note", "severity": "Minor",
             "docSection": "Goals", "summary": "add detail"},
            {"file": "plan.md", "title": "nit", "severity": "Nit", "dimension": "Data flow"},
        ]},
    ]), encoding="utf-8")
    out = rh.collect_nonblocking(str(records_path))
    assert out["ok"]
    assert len(out["findings"]) == 2
    assert {f["title"] for f in out["findings"]} == {"minor note", "nit"}
    assert out["findings"][0]["planSection"] == "Goals"
    assert out["findings"][1]["planSection"] == "Data flow"


def test_collect_unreadable_records_returns_structured_failure(tmp_path):
    rh = _load("review_handoff")
    path = tmp_path / "round-records.json"
    path.write_text("[", encoding="utf-8")
    out = rh.collect_nonblocking(str(path))
    assert not out["ok"]
    assert out["reason"].startswith("unreadable:")


def test_write_scrubs_finding_text_before_it_reaches_disk(tmp_path):
    # plan-handoff.json is a durable FILE, not a journal event, but it carries the same
    # free-text finding titles a courier round-tripped — Bearer-token shape matches an existing
    # pr_comment._SCRUB_PATTERNS pattern, same fixture review_park.py's scrub test uses (#397).
    rh = _load("review_handoff")
    rh.write_handoff(str(tmp_path), "wi-1", [
        {"file": "plan.md", "title": "rotate the leaked token: Bearer abcdef0123456789",
         "severity": "Minor", "planSection": "Security"}])
    data = json.loads(open(os.path.join(str(tmp_path), "plan-handoff.json")).read())
    entry = data["findings"][0]
    assert "abcdef0123456789" not in entry["text"]
    assert "[REDACTED]" in entry["text"]
    # identity derives from the same scrubbed title/summary label — both durable fields must redact.
    assert "abcdef0123456789" not in entry["identity"]


def test_write_scrubs_summary_only_identity_before_it_reaches_disk(tmp_path):
    # When only summary carries the secret, identity must still redact — not only the text field.
    rh = _load("review_handoff")
    rh.write_handoff(str(tmp_path), "wi-1", [
        {"file": "plan.md", "summary": "rotate the leaked token: Bearer abcdef0123456789",
         "severity": "Minor", "planSection": "Security"}])
    entry = json.loads(open(os.path.join(str(tmp_path), "plan-handoff.json")).read())["findings"][0]
    assert "abcdef0123456789" not in entry["text"]
    assert "abcdef0123456789" not in entry["identity"]
