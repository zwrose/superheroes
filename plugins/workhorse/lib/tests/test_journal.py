# plugins/workhorse/lib/tests/test_journal.py
import journal


def test_append_read_roundtrip_monotonic_seq(tmp_path):
    e = str(tmp_path / "events.jsonl")
    journal.append(e, "run_started", root=str(tmp_path))
    journal.append(e, "step_completed", step="3", detail="PR #1 opened", root=str(tmp_path))
    evs = journal.read_events(e)
    assert [x["seq"] for x in evs] == [1, 2]
    assert evs[1]["type"] == "step_completed" and evs[1]["step"] == "3"


def test_read_events_skips_torn_tail(tmp_path):
    e = tmp_path / "events.jsonl"
    e.write_text('{"seq":1,"type":"run_started"}\n{"seq":2,"type":"step_ent')  # torn line
    evs = journal.read_events(str(e))
    assert len(evs) == 1 and evs[0]["seq"] == 1


def test_detail_is_scrubbed_fail_closed(tmp_path, monkeypatch):
    # force the scrubber to fail -> the durable write must store the redaction note, never raw
    monkeypatch.setattr(journal.readout, "scrub",
                        lambda t, root=None: ("[omitted — scrub failed]", False))
    e = str(tmp_path / "events.jsonl")
    journal.append(e, "error", detail="SECRET=abc123", root=str(tmp_path))
    assert "SECRET" not in open(e).read()
    assert "[omitted — scrub failed]" in open(e).read()


def test_append_surfaces_durable_write_failure(tmp_path, monkeypatch):
    import pytest
    monkeypatch.setattr(journal.readout, "scrub", lambda t, root=None: (t, True))
    monkeypatch.setattr(journal.os, "fsync",
                        lambda fd: (_ for _ in ()).throw(OSError("ENOSPC")))
    with pytest.raises(journal.DurableWriteError):     # a failed durable write -> orchestrator parks
        journal.append(str(tmp_path / "events.jsonl"), "run_started", root=str(tmp_path))


def test_ci_attempts_replay_counts_every_recorded_attempt(tmp_path, monkeypatch):
    monkeypatch.setattr(journal.readout, "scrub", lambda t, root=None: (t, True))
    e = str(tmp_path / "events.jsonl")
    journal.append(e, "ci_fix_attempt", payload={"round": 1, "failing": ["lint"]}, root=str(tmp_path))
    journal.append(e, "ci_fix_attempt", payload={"round": 2, "failing": ["lint", "unit"]}, root=str(tmp_path))
    rounds, history = journal.ci_attempts(e)
    assert rounds == 2 and history == [["lint"], ["lint", "unit"]]


def test_ci_attempts_over_counts_a_torn_tail_failsafe(tmp_path, monkeypatch):
    monkeypatch.setattr(journal.readout, "scrub", lambda t, root=None: (t, True))
    e = str(tmp_path / "events.jsonl")
    journal.append(e, "ci_fix_attempt", payload={"round": 1, "failing": ["lint"]}, root=str(tmp_path))
    with open(e, "a", encoding="utf-8") as fh:
        fh.write('{"type":"ci_fix_attempt","payload":{"round":2,"fail')   # torn trailing line
    rounds, _ = journal.ci_attempts(e)
    assert rounds == 2   # 1 parsed + 1 conservative for the torn tail (NEVER under-counts)


def test_render_brief_has_required_sections(tmp_path, monkeypatch):
    monkeypatch.setattr(journal.readout, "scrub", lambda t, root=None: (t, True))
    e = str(tmp_path / "events.jsonl")
    journal.append(e, "run_started", root=str(tmp_path))
    brief = str(tmp_path / "resume-brief.md")
    ckpt = {"workItem": "wi", "branch": "superheroes/wi-abc", "phase": "verify",
            "lastGoodStep": "5", "pr": {"url": "http://x/1"}}
    journal.render_brief(brief, ckpt, {"ci": "green", "dev_server": "up"}, e, root=str(tmp_path))
    body = open(brief).read()
    for section in ("## Run", "## Where it was", "## Confirmed done", "## Next", "## Notices"):
        assert section in body


def test_append_open_failure_surfaces_durable_write(tmp_path, monkeypatch):
    # os.open (not just fsync) failing must also park, not crash uncaught.
    import pytest
    monkeypatch.setattr(journal.os, "open",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("EACCES")))
    with pytest.raises(journal.DurableWriteError):
        journal.append(str(tmp_path / "events.jsonl"), "run_started", root=str(tmp_path))


def test_render_brief_scrubs_world_facts(tmp_path, monkeypatch):
    # World facts are durable free-text -> scrubbed fail-closed before landing in the brief.
    monkeypatch.setattr(journal.readout, "scrub", lambda t, root=None: ("[redacted]", False))
    brief = str(tmp_path / "resume-brief.md")
    journal.render_brief(brief, {"workItem": "wi"},
                         {"ci": "TOKEN=sekret", "dev_server": "up"},
                         str(tmp_path / "events.jsonl"), root=str(tmp_path))
    body = open(brief).read()
    assert "TOKEN" not in body and "[redacted]" in body


def test_render_brief_absent_world_uses_sentinel(tmp_path, monkeypatch):
    # Empty world (the PreCompact path) shows the absent sentinel, not literal "None".
    monkeypatch.setattr(journal.readout, "scrub", lambda t, root=None: (t, True))
    brief = str(tmp_path / "resume-brief.md")
    journal.render_brief(brief, {"workItem": "wi"}, {}, str(tmp_path / "events.jsonl"),
                         root=str(tmp_path))
    body = open(brief).read()
    assert "- PR: —" in body          # the world PR field uses the sentinel, not literal "None"
