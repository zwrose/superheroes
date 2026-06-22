# plugins/superheroes/lib/tests/test_journal_phase_record.py
import journal


def test_phase_record_is_an_accepted_event_type(tmp_path):
    assert "phase_record" in journal.EVENT_TYPES


def test_phase_record_append_and_read_roundtrip(tmp_path):
    ev = str(tmp_path / "events.jsonl")
    journal.append(
        ev, "phase_record",
        payload={"phase": "plan", "gate": "passed", "confidence": "high", "assumptions": []},
        root=str(tmp_path),
    )
    rows = journal.read_events(ev)
    assert rows[-1]["type"] == "phase_record"
    assert rows[-1]["payload"]["phase"] == "plan"
    assert rows[-1]["payload"]["gate"] == "passed"
    assert rows[-1]["payload"]["confidence"] == "high"
    assert rows[-1]["payload"]["assumptions"] == []
