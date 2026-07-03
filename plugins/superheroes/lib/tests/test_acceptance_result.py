import os, sys, json, tempfile, shutil
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import acceptance_result as ar

FULL = dict(
    verdict="fail", reason="terminal was parked", pr_link="https://x/pr/1",
    phases=["plan", "tasks"], spend=1.25, spend_partial=False, elapsed_sec=42.0,
    launched_at="2026-07-02T00:00:00Z", terminated_at="2026-07-02T00:01:00Z",
    retried=False, attempts=[{"stamp": "s1", "verdict": "fail"}],
    cleaned_up=["branch wi-s1"], left_behind=[],
)


def test_write_then_read_roundtrips_with_schema_version():
    d = tempfile.mkdtemp()
    try:
        p = ar.write_record(dict(FULL), d)
        assert os.path.isfile(p)
        rec = ar.read_record(d)
        assert rec["schemaVersion"] == ar.SCHEMA_VERSION
        assert rec["verdict"] == "fail"
        assert rec["attempts"][0]["stamp"] == "s1"
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_missing_required_element_is_rejected():
    d = tempfile.mkdtemp()
    try:
        bad = dict(FULL); del bad["elapsed_sec"]
        try:
            ar.write_record(bad, d)
            assert False, "expected ValueError for a record missing a required element"
        except ValueError:
            pass
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_read_missing_record_returns_none_never_raises():
    d = tempfile.mkdtemp()
    try:
        assert ar.read_record(d) is None
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_read_record_schema_version_mismatch_returns_none():
    # test-002: the schemaVersion guard is the load-bearing rollback fence for the FR-5
    # durable record. A stale-schema record must never be read as current.
    d = tempfile.mkdtemp()
    try:
        path = ar.write_record(dict(FULL), d)
        with open(path, encoding="utf-8") as fh:
            rec = json.load(fh)
        rec["schemaVersion"] = ar.SCHEMA_VERSION + 1
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(rec, fh)
        assert ar.read_record(d) is None
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_read_record_missing_schema_version_key_returns_none():
    d = tempfile.mkdtemp()
    try:
        path = ar.write_record(dict(FULL), d)
        with open(path, encoding="utf-8") as fh:
            rec = json.load(fh)
        del rec["schemaVersion"]
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(rec, fh)
        assert ar.read_record(d) is None
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_read_record_corrupt_json_returns_none_never_raises():
    # test-002: the corrupt-JSON except (OSError, ValueError) branch must never raise —
    # a regression narrowing it to drop ValueError would break the never-raises contract.
    d = tempfile.mkdtemp()
    try:
        path = os.path.join(d, ar.RECORD_NAME)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("{ this is not valid json ]")
        assert ar.read_record(d) is None
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_render_report_has_all_four_elements():
    out = ar.render_report(dict(FULL))
    assert "fail" in out.lower()                 # verdict
    assert "terminal was parked" in out          # reason
    assert "record" in out.lower()               # where the record lives
    assert ("cleaned" in out.lower() or "left behind" in out.lower())  # cleaned-up/left-behind


def test_render_report_notes_partial_spend_when_flagged():
    r = dict(FULL); r["spend_partial"] = True
    assert "partial" in ar.render_report(r).lower()
