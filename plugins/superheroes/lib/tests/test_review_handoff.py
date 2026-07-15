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


def test_collect_nonblocking_unions_all_rounds_while_blocking_is_terminal_only(tmp_path):
    # Pins the INTENTIONAL asymmetry (see collect_nonblocking's docstring): advisories are a
    # STREAM across all rounds — under scoped-round economics a dimension that goes clean is
    # skipped later and re-reports nothing, so a round-1 advisory must survive to the hand-off
    # even when the terminal round no longer carries it. Blocking findings are STATE — terminal
    # round only. Do not "fix" either side to match the other.
    rh = _load("review_handoff")
    records_path = tmp_path / "round-records.json"
    records_path.write_text(json.dumps([
        {"round": 1, "findings": [
            {"file": "plan.md", "title": "early advisory from a dimension later skipped",
             "severity": "Minor", "docSection": "Goals"},
            {"file": "plan.md", "title": "round-1 blocker, later fixed", "severity": "Important"},
        ]},
        # terminal round: the advisory's dimension was skipped (re-reports nothing); a new blocker
        {"round": 2, "findings": [
            {"file": "plan.md", "title": "terminal blocker", "severity": "Critical"},
        ]},
    ]), encoding="utf-8")
    nonblocking = rh.collect_nonblocking(str(records_path))
    assert nonblocking["ok"]
    assert {f["title"] for f in nonblocking["findings"]} == {
        "early advisory from a dimension later skipped"}
    blocking = rh.collect_blocking(str(records_path))
    assert blocking["ok"]
    # terminal-only: the fixed round-1 blocker does NOT ride; only the terminal round's does
    assert {f["title"] for f in blocking["findings"]} == {"terminal blocker"}


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


def test_two_run_rerun_atomically_replaces_handoff_with_distinct_findings_once(tmp_path):
    """UFR-3 across re-runs: a re-review's write atomically REPLACES plan-handoff.json —
    the file holds the new run's full deduped set, each distinct finding exactly once,
    never an append/union with run 1's list."""
    rh = _load("review_handoff")
    # run 1: two advisories
    rh.write_handoff(str(tmp_path), "wi-1", [
        {"file": "plan.md", "title": "no named unit test", "severity": "Minor",
         "planSection": "Testing", "summary": "add a unit test for option A"},
        {"file": "plan.md", "title": "two literals for retry", "severity": "Minor",
         "planSection": "Data flow", "summary": "retry constant appears twice"},
    ])
    # run 2 (re-review): overlaps on one finding (reworded case → same identity after
    # normalization), drops the other, adds a new one — plus an in-run duplicate
    out = rh.write_handoff(str(tmp_path), "wi-1", [
        {"file": "plan.md", "title": "No Named UNIT Test", "severity": "Minor",
         "planSection": "Testing", "summary": "still worth a unit test"},
        {"file": "plan.md", "title": "no named unit test", "severity": "Minor",
         "planSection": "Testing", "summary": "dup within run 2"},
        {"file": "plan.md", "title": "park note lacks decision list", "severity": "Minor",
         "planSection": "Legibility", "summary": "new advisory from run 2"},
    ])
    assert out["ok"] and out["counts"]["distinct"] == 2
    data = json.loads(open(os.path.join(str(tmp_path), "plan-handoff.json")).read())
    idents = [e["identity"] for e in data["findings"]]
    # each distinct finding exactly once; run 1's non-overlapping entry is GONE (replace, not union)
    assert len(idents) == len(set(idents)) == 2
    assert data["counts"]["distinct"] == 2
    assert not any("two literals" in e["identity"] for e in data["findings"])
    assert any("park note lacks decision list" in e["identity"] for e in data["findings"])
    # no partial/temp residue from the atomic replace
    assert sorted(f for f in os.listdir(str(tmp_path)) if "handoff" in f) == ["plan-handoff.json"]
