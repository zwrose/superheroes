# plugins/superheroes/lib/tests/test_journal.py
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


def test_phase_cost_is_a_valid_additive_event_type(tmp_path, monkeypatch):
    # #130: token telemetry extends the §4.6 vocabulary additively (no schemaVersion bump). A
    # phase_cost event carries structured non-secret accounting written as-is (like ci_fix_attempt).
    monkeypatch.setattr(journal.readout, "scrub", lambda t, root=None: (t, True))
    e = str(tmp_path / "events.jsonl")
    payload = {"phase": "workhorse",
               "dispatches": {"total": 12, "byModel": {"claude-opus-4-8": 3, "claude-haiku-4-5-20251001": 9}},
               "tokens": {"output": 84000, "input": None, "measured": True, "source": "budget"}}
    journal.append(e, "phase_cost", payload=payload, root=str(tmp_path))
    evs = journal.read_events(e)
    assert evs[0]["type"] == "phase_cost"
    assert evs[0]["payload"]["dispatches"]["total"] == 12
    assert evs[0]["payload"]["tokens"]["output"] == 84000


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


def test_render_brief_pr_dict_ready_vs_draft(tmp_path, monkeypatch):
    # The world-PR-dict branch: isDraft False -> "ready", True -> "draft".
    monkeypatch.setattr(journal.readout, "scrub", lambda t, root=None: (t, True))
    e = str(tmp_path / "events.jsonl")
    ready = str(tmp_path / "ready.md")
    journal.render_brief(ready, {}, {"pr": {"isDraft": False}}, e, root=str(tmp_path))
    assert "- PR: ready" in open(ready).read()
    draft = str(tmp_path / "draft.md")
    journal.render_brief(draft, {}, {"pr": {"isDraft": True}}, e, root=str(tmp_path))
    assert "- PR: draft" in open(draft).read()


def test_append_rejects_unknown_event_type(tmp_path):
    # The EVENT_TYPES guard fails closed: a typo'd type would otherwise under-count the
    # ci_fix_attempt bound. It must raise (park) before any write.
    import pytest
    e = str(tmp_path / "events.jsonl")
    with pytest.raises(journal.DurableWriteError):
        journal.append(e, "ci_fix_attemp", root=str(tmp_path))   # typo
    import os
    assert not os.path.exists(e)          # raised before any I/O — nothing written


def test_external_dispatch_event_appends_and_reads(tmp_path):
    import journal
    p = str(tmp_path / "events.jsonl")
    journal.append(p, "external_dispatch",
                   payload={"engine": "codex", "effort": "high", "roleKind": "build",
                            "verify": "passed", "outcome": "ok"},
                   root=str(tmp_path))
    evs = journal.read_events(p)
    assert len(evs) == 1
    ev = evs[0]
    assert ev["type"] == "external_dispatch"
    # payload is written AS-IS (non-secret; the plan's §4.6)
    assert ev["payload"] == {"engine": "codex", "effort": "high", "roleKind": "build",
                              "verify": "passed", "outcome": "ok"}


def test_unknown_event_type_still_raises_durable_write_error(tmp_path):
    import journal
    import pytest
    p = str(tmp_path / "events.jsonl")
    with pytest.raises(journal.DurableWriteError):
        journal.append(p, "not_a_real_event", root=str(tmp_path))


def test_journal_entry_cli_writes_external_dispatch_type(tmp_path, monkeypatch):
    # The JS seam (Task 10) shells journal_entry.py --event-type external_dispatch; the written
    # line's `type` must be external_dispatch (not the hardcoded phase_record).
    import json as _json
    import os as _os
    import subprocess as _sp
    import sys as _sys
    import control_plane
    import journal
    _lib = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..")
    monkeypatch.chdir(tmp_path)   # journal_entry.py uses os.getcwd() for the control-plane paths
    out = _sp.run(
        [_sys.executable, _os.path.join(_lib, "journal_entry.py"),
         "--work-item", "wi-x", "--event-type", "external_dispatch",
         "--payload", _json.dumps({"engine": "codex", "effort": "high", "roleKind": "build",
                                   "verify": "pending", "outcome": "ok"})],
        capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert _json.loads(out.stdout) == {"ok": True}
    events = control_plane.paths(str(tmp_path), "wi-x")["events"]
    evs = journal.read_events(events)
    assert evs[-1]["type"] == "external_dispatch"
    assert evs[-1]["payload"]["engine"] == "codex"


def test_permission_denied_is_a_valid_event_type(tmp_path):
    p = str(tmp_path / "events.jsonl")
    journal.append(p, "permission_denied", step="build:task-3", detail={"command": "python3 -c x"})
    lines = open(p).read().splitlines()
    assert any('"type": "permission_denied"' in l for l in lines)


def test_courier_declined_is_a_valid_event_type(tmp_path):
    # #402 Part B: the decline-journal seam (showrunner _defaultDeclineRecorder) shells
    # journal.append(events, "courier_declined", step=<label>, detail={"reason": <scrubbed>}). Prove the
    # REAL append path succeeds and the event is durable — the smokes inject an observer that bypasses
    # this, so without a real-path test a missing EVENT_TYPES entry would silently drop every decline.
    p = str(tmp_path / "events.jsonl")
    journal.append(p, "courier_declined", step="save phase progress",
                   detail={"reason": "permission for this action was denied"}, root=str(tmp_path))
    evs = journal.read_events(p)
    assert evs[-1]["type"] == "courier_declined"
    assert evs[-1]["step"] == "save phase progress"
    # detail is scrubbed to a string (journal._scrub stringifies then readout-scrubs the whole value).
    assert "denied" in evs[-1]["detail"]


def test_courier_declined_is_a_known_event_type():
    # An unknown type fails closed (DurableWriteError) and — because the decline recorder is fail-open —
    # would be swallowed, dropping the decline. courier_declined MUST be registered.
    assert "courier_declined" in journal.EVENT_TYPES


def test_allowance_fired_is_a_valid_event_type(tmp_path):
    # #149 auditability NFR: an automatic ALLOWANCE (not just a denial) is recorded with a
    # structured, non-secret payload written AS-IS — the command HASH, never the raw command
    # text — so every auto-allowance is visible in the run's records.
    p = str(tmp_path / "events.jsonl")
    payload = {"reason": "routine:test-run", "command_sha256": "0123456789abcdef", "cwd": "/w"}
    journal.append(p, "allowance_fired", payload=payload, root=str(tmp_path))
    evs = journal.read_events(p)
    assert evs[-1]["type"] == "allowance_fired"
    assert evs[-1]["payload"] == payload      # written as-is (non-secret)


def test_allowance_fired_is_a_known_event_type():
    # An unknown type fails closed (DurableWriteError); allowance_fired must be registered.
    assert "allowance_fired" in journal.EVENT_TYPES


def test_dense_seq_false_omits_seq_and_skips_the_whole_file_read(tmp_path, monkeypatch):
    # premortem-001 / #379: the multi-writer checkout allowance trail appends with
    # dense_seq=False. The event must carry `ts` + `type` (readable/roundtrippable) but NO `seq`,
    # and the append must NOT re-read the whole file to compute one (the O(n^2) hot-path cost the
    # trail routing avoids). Default (dense_seq=True) still stamps a dense seq.
    p = str(tmp_path / "trail.jsonl")
    calls = []
    real_next_seq = journal._next_seq
    monkeypatch.setattr(journal, "_next_seq",
                        lambda path: calls.append(path) or real_next_seq(path))
    journal.append(p, "allowance_fired", payload={"reason": "r"}, dense_seq=False)
    journal.append(p, "allowance_fired", payload={"reason": "r"}, dense_seq=False)
    assert calls == [], "dense_seq=False must not read the file to compute a seq"
    evs = journal.read_events(p)
    assert len(evs) == 2
    assert all("seq" not in e for e in evs)
    assert all(e["ts"] and e["type"] == "allowance_fired" for e in evs)
    # Default keeps the dense seq (and does read the file).
    journal.append(p, "allowance_fired", payload={"reason": "r"})
    assert calls == [p], "dense_seq=True (default) computes a dense seq"
    assert journal.read_events(p)[-1]["seq"] == 3


def test_unknown_event_type_still_parks(tmp_path):
    p = str(tmp_path / "events.jsonl")
    try:
        journal.append(p, "not_a_real_type")
        assert False, "expected DurableWriteError"
    except journal.DurableWriteError:
        pass


def test_journal_entry_cli_step_detail_passthrough(tmp_path, monkeypatch):
    # test-001 (UFR-3 / code-001): build_phase.js shells journal_entry.py with --step/--detail
    # (and NO --payload) to record a build-step permission_denied event. Exercise the real CLI
    # argparse end-to-end and confirm both flags land at top level in the written event — a broken
    # flag name here would silently drop the build-denial disclosure (and the ship gate's second
    # denial carrier) with no other test failing.
    import json as _json
    import os as _os
    import subprocess as _sp
    import sys as _sys
    import control_plane
    import journal
    _lib = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..")
    monkeypatch.chdir(tmp_path)
    out = _sp.run(
        [_sys.executable, _os.path.join(_lib, "journal_entry.py"),
         "--work-item", "wi-x", "--event-type", "permission_denied",
         "--step", "build:task-3", "--detail", "could not run migration"],
        capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert _json.loads(out.stdout) == {"ok": True}
    evs = journal.read_events(control_plane.paths(str(tmp_path), "wi-x")["events"])
    assert evs[-1]["type"] == "permission_denied"
    assert evs[-1]["step"] == "build:task-3"
    assert evs[-1]["detail"] == "could not run migration"


def test_journal_entry_cli_defaults_to_phase_record(tmp_path, monkeypatch):
    # Back-compat: NO --event-type -> phase_record (the existing behavior is byte-preserved).
    import json as _json
    import os as _os
    import subprocess as _sp
    import sys as _sys
    import control_plane
    import journal
    _lib = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..")
    monkeypatch.chdir(tmp_path)
    out = _sp.run(
        [_sys.executable, _os.path.join(_lib, "journal_entry.py"),
         "--work-item", "wi-y", "--payload", _json.dumps({"phase": "build", "ok": True})],
        capture_output=True, text=True)
    assert out.returncode == 0 and _json.loads(out.stdout) == {"ok": True}
    evs = journal.read_events(control_plane.paths(str(tmp_path), "wi-y")["events"])
    assert evs[-1]["type"] == "phase_record"


def test_phases_skipped_event_is_recorded_with_payload(tmp_path, monkeypatch):
    # #25: the quick route's skipped-phase record rides the journal_entry.py seam with a structured,
    # non-secret payload written AS-IS — so the skip is durable and honest, never silently absent.
    import json as _json
    import os as _os
    import subprocess as _sp
    import sys as _sys
    import control_plane
    import journal
    _lib = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..")
    monkeypatch.chdir(tmp_path)
    payload = {"route": "quick", "skipped": ["plan", "review-plan", "tasks", "review-tasks"],
               "entryPhase": "workhorse"}
    out = _sp.run(
        [_sys.executable, _os.path.join(_lib, "journal_entry.py"),
         "--work-item", "wi-q", "--event-type", "phases_skipped", "--payload", _json.dumps(payload)],
        capture_output=True, text=True)
    assert out.returncode == 0 and _json.loads(out.stdout) == {"ok": True}
    evs = journal.read_events(control_plane.paths(str(tmp_path), "wi-q")["events"])
    assert evs[-1]["type"] == "phases_skipped"
    assert evs[-1]["payload"] == payload


def test_phases_skipped_is_a_known_event_type():
    # An unknown type would fail closed (DurableWriteError); phases_skipped must be registered.
    assert "phases_skipped" in journal.EVENT_TYPES


def test_final_review_handoff_is_a_known_event_type():
    # #381: the whole-branch final-review handoff breadcrumb must be in the vocabulary before
    # journal_entry.py can append it (unknown types fail closed with DurableWriteError).
    assert "final_review_handoff" in journal.EVENT_TYPES


def test_new_doc_review_event_types_are_accepted(tmp_path):
    import importlib.util, os
    lib = os.path.join(os.path.dirname(__file__), "..")
    spec = importlib.util.spec_from_file_location("journal", os.path.join(lib, "journal.py"))
    journal = importlib.util.module_from_spec(spec); spec.loader.exec_module(journal)
    events = str(tmp_path / "events.jsonl")
    for et in ("routed_forward", "review_convergence", "handoff_provided"):
        journal.append(events, et, payload={"doc": "plan"}, root=str(tmp_path))
    kinds = [e.get("type") for e in journal.read_events(events)]
    assert kinds == ["routed_forward", "review_convergence", "handoff_provided"]


def test_journal_entry_cli_writes_final_review_handoff(tmp_path, monkeypatch):
    # #381: build_phase.js shells journal_entry.py --event-type final_review_handoff; prove the
    # CLI append succeeds and the event line is durable (not a mock — real journal_entry.py path).
    import json as _json
    import os as _os
    import subprocess as _sp
    import sys as _sys
    import control_plane
    import journal
    _lib = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..")
    wi = "wi-final-review-handoff-%d" % _os.getpid()
    monkeypatch.chdir(tmp_path)
    payload = {
        "branch": "feat/x",
        "open_findings_count": 1,
        "open_findings": [{"file": "a.js", "line": 1, "title": "blocker", "severity": "Critical"}],
        "reason": "round cap",
        "fix_dispatched": True,
        "fix_fixed": ["blocker"],
        "post_fix_verify": "skipped",
        "handoff": "review-code",
    }
    out = _sp.run(
        [_sys.executable, _os.path.join(_lib, "journal_entry.py"),
         "--work-item", wi, "--event-type", "final_review_handoff",
         "--step", "final_review",
         "--detail", "handoff to review-code",
         "--payload", _json.dumps(payload)],
        capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert _json.loads(out.stdout) == {"ok": True}
    events = control_plane.paths(str(tmp_path), wi)["events"]
    evs = journal.read_events(events)
    assert evs[-1]["type"] == "final_review_handoff"
    assert evs[-1]["step"] == "final_review"
    assert evs[-1]["payload"]["handoff"] == "review-code"
    assert _os.path.exists(events)
    assert any('"type": "final_review_handoff"' in line for line in open(events).read().splitlines())


def test_idem_key_dedupes_a_repeated_append(tmp_path):
    # #350 Part A (the doubled-line signature): a courier-chain retry (_execJson) re-runs
    # journal_entry.py AFTER the first append already landed, because a journal append is not
    # idempotent. An `idem` key makes the SECOND identical append a no-op — the same line cannot
    # double. Two calls with the same idem -> exactly one event; the idem value is recorded top-level.
    p = str(tmp_path / "events.jsonl")
    payload = {"engine": "codex", "roleKind": "review", "outcome": "unreadable",
               "outPath": "/tmp/engine-cursor-build-1.run.68417.out", "outBytes": 0}
    journal.append(p, "external_dispatch", payload=payload, root=str(tmp_path), idem="disp-7")
    journal.append(p, "external_dispatch", payload=payload, root=str(tmp_path), idem="disp-7")
    evs = journal.read_events(p)
    assert len(evs) == 1, "the idem retry must be a no-op — one line, never two"
    assert evs[0]["idem"] == "disp-7"
    assert evs[0]["seq"] == 1


def test_distinct_idem_keys_both_append(tmp_path):
    # Idempotency is per-key: two genuinely-distinct dispatches that happen to carry byte-identical
    # payloads (e.g. two failed dispatches with the same outcome — the #378 re-execute case) MUST each
    # journal. A content-derived key would wrongly collapse them; a per-call nonce does not.
    p = str(tmp_path / "events.jsonl")
    payload = {"engine": "codex", "roleKind": "review", "outcome": "unreadable"}
    journal.append(p, "external_dispatch", payload=payload, root=str(tmp_path), idem="disp-1")
    journal.append(p, "external_dispatch", payload=payload, root=str(tmp_path), idem="disp-2")
    evs = journal.read_events(p)
    assert len(evs) == 2
    assert [e["seq"] for e in evs] == [1, 2]
    assert [e["idem"] for e in evs] == ["disp-1", "disp-2"]


def test_idem_absent_when_not_supplied(tmp_path):
    # Backward compatibility: an append with no idem writes NO idem field (pre-#350 byte shape).
    p = str(tmp_path / "events.jsonl")
    journal.append(p, "external_dispatch", payload={"engine": "codex"}, root=str(tmp_path))
    evs = journal.read_events(p)
    assert "idem" not in evs[0]


def test_journal_entry_cli_idem_dedupes_a_rerun(tmp_path, monkeypatch):
    # The JS seam (_journalExternal) shells journal_entry.py --idem <nonce>; _execJson re-runs the
    # SAME command on a courier stdout-drop. Two CLI runs with the same --idem -> one event.
    import json as _json
    import os as _os
    import subprocess as _sp
    import sys as _sys
    import control_plane
    _lib = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..")
    monkeypatch.chdir(tmp_path)
    args = [_sys.executable, _os.path.join(_lib, "journal_entry.py"),
            "--work-item", "wi-idem", "--event-type", "external_dispatch",
            "--idem", "cursor-review-r4-1",
            "--payload", _json.dumps({"engine": "cursor", "outcome": "unreadable"})]
    for _ in range(2):
        out = _sp.run(args, capture_output=True, text=True)
        assert out.returncode == 0, out.stderr
        assert _json.loads(out.stdout) == {"ok": True}
    events = control_plane.paths(str(tmp_path), "wi-idem")["events"]
    evs = journal.read_events(events)
    assert len([e for e in evs if e.get("type") == "external_dispatch"]) == 1


def test_dispatch_retried_is_a_valid_event_type(tmp_path):
    # #350 Part B (the silent re-execution disclosure): a re-execute-and-discard decision journals a
    # loud dispatch_retried event carrying the cause + the discarded result's summary/hash. Prove the
    # REAL append path succeeds so a missing EVENT_TYPES entry can't silently drop the disclosure.
    p = str(tmp_path / "events.jsonl")
    payload = {"cause": "escalation:reviewer->reviewer-deep", "reviewer": "code", "round": 4,
               "discardedFindings": 2, "discardedHash": "abc123"}
    journal.append(p, "dispatch_retried", step="review:code", payload=payload, root=str(tmp_path))
    evs = journal.read_events(p)
    assert evs[-1]["type"] == "dispatch_retried"
    assert evs[-1]["payload"]["discardedFindings"] == 2


def test_dispatch_retried_is_a_known_event_type():
    assert "dispatch_retried" in journal.EVENT_TYPES


def test_max_idem_ordinal_seeds_a_resumed_dispatch_counter(tmp_path):
    # #350 Part A resume-safety: the per-process dispatch-nonce counter is SEEDED from the journal's max
    # `<prefix>:d<N>` ordinal so a resumed run continues past the pre-crash tail (never re-mints a
    # colliding d1..dN that journal.append would silently dedupe away).
    p = str(tmp_path / "events.jsonl")
    journal.append(p, "external_dispatch", payload={"o": 1}, root=str(tmp_path), idem="wi-x:d1")
    journal.append(p, "external_dispatch", payload={"o": 2}, root=str(tmp_path), idem="wi-x:d2")
    journal.append(p, "external_dispatch", payload={"o": 9}, root=str(tmp_path), idem="wi-x:d9")
    # a DIFFERENT prefix must not bleed into the max (Part B's retry:... idems, another work-item, etc.)
    journal.append(p, "dispatch_retried", step="review:code", payload={"c": 1}, root=str(tmp_path),
                   idem="retry:code:r1:escalation:abc")
    journal.append(p, "external_dispatch", payload={"o": 4}, root=str(tmp_path), idem="wi-other:d4")
    assert journal.max_idem_ordinal(p, "wi-x") == 9
    assert journal.max_idem_ordinal(p, "wi-other") == 4
    assert journal.max_idem_ordinal(p, "wi-absent") == 0    # a fresh run: no prior ordinal


def test_max_idem_ordinal_zero_on_missing_or_unreadable_journal(tmp_path):
    # A fresh run (no journal yet) seeds 0, so its first dispatch mints d1.
    assert journal.max_idem_ordinal(str(tmp_path / "nope.jsonl"), "wi-x") == 0


def test_max_idem_ordinal_ignores_malformed_ordinals(tmp_path):
    # Only a strict `<prefix>:d<digits>` idem counts; a look-alike must not seed the counter.
    p = str(tmp_path / "events.jsonl")
    journal.append(p, "external_dispatch", payload={"o": 1}, root=str(tmp_path), idem="wi-x:dABC")
    journal.append(p, "external_dispatch", payload={"o": 2}, root=str(tmp_path), idem="wi-x:d3x")
    journal.append(p, "external_dispatch", payload={"o": 3}, root=str(tmp_path), idem="wi-x:d7")
    assert journal.max_idem_ordinal(p, "wi-x") == 7


def test_journal_entry_cli_max_idem_prefix_query(tmp_path, monkeypatch):
    # The JS seam (_maxDispatchNonce) shells journal_entry.py --max-idem-prefix; it must print the max
    # ordinal and make NO append.
    import json as _json
    import os as _os
    import subprocess as _sp
    import sys as _sys
    import control_plane
    _lib = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..")
    monkeypatch.chdir(tmp_path)
    events = control_plane.paths(str(tmp_path), "wi-q")["events"]
    journal.append(events, "external_dispatch", payload={"o": 1}, root=str(tmp_path), idem="wi-q:d5")
    before = len(journal.read_events(events))
    out = _sp.run([_sys.executable, _os.path.join(_lib, "journal_entry.py"),
                   "--work-item", "wi-q", "--max-idem-prefix", "wi-q"],
                  capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert _json.loads(out.stdout) == {"ok": True, "max": 5}
    assert len(journal.read_events(events)) == before, "the query must NOT append"
