import json
import os
import time

import control_plane
import hostinfo
import ref_lock
import run_watch


WI = "live-watch-152"


def _write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh)


def _write_events(path, events):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for event in events:
            fh.write(json.dumps(event) + "\n")


def _make_tasks_doc(root, work_item, count=3):
    d = root / "docs" / "superheroes" / work_item
    d.mkdir(parents=True)
    (d / "spec.md").write_text("---\n---\n", encoding="utf-8")
    body = "\n".join(f"### Task {i}: Thing {i}" for i in range(1, count + 1))
    (d / "tasks.md").write_text("---\n---\n\n" + body + "\n", encoding="utf-8")


def _make_review_dir(tmp_path, monkeypatch, phase="review-code"):
    review_root = tmp_path / "review-root"
    monkeypatch.setattr(run_watch, "REVIEW_ROOT", str(review_root))
    run_dir = review_root / f"showrunner-{WI}-{phase}-abc123"
    run_dir.mkdir(parents=True)
    _write_json(run_dir / "round-records.json", [
        {"schemaVersion": 2, "round": 1, "dimensions": {"code": {"status": "clean"}}},
        {
            "schemaVersion": 2,
            "round": 2,
            "dimensions": {
                "code": {"status": "clean", "blockingCount": 0},
                "security": {
                    "status": "findings",
                    "blockingCount": 1,
                    "findings": [{"title": "buffer-overflow", "severity": "Important"}],
                },
                "architecture": {"status": "clean", "blockingCount": 0},
            },
        },
    ])
    _write_json(run_dir / "review-telemetry.json", {
        "terminal": "unclean",
        "roundCount": 2,
    })
    _write_json(run_dir / "terminal-record.json", {
        "terminal": "unclean",
        "gate": "changes-requested",
        "round": 2,
        "reason": "fixing",
    })
    return run_dir


def _seed_happy_run(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    _make_tasks_doc(root, WI, count=3)
    paths = control_plane.paths(str(root), WI)
    _write_json(paths["checkpoint"], {
        "schemaVersion": 2,
        "workItem": WI,
        "phase": "review-code",
        "gates": {"review": "passed", "test": "pending"},
        "lastGoodStep": 5,
        "lastGoodPhase": "review-code",
        "updatedAt": "2026-07-03T14:39:00Z",
    })
    _write_json(os.path.join(paths["issue_dir"], "build-state.json"), {
        "reviewed": {"1": "passed", "2": "passed"},
        "built": {"1": "passed"},
        "final_review": {"clean": False},
    })
    _write_events(paths["events"], [
        {"ts": "2026-07-03T14:32:01Z", "seq": 1, "type": "run_started", "detail": WI},
        {"ts": "2026-07-03T14:35:12Z", "seq": 2, "type": "step_entered", "step": "review-code"},
        {"ts": "2026-07-03T14:37:00Z", "seq": 3, "type": "parked", "detail": "needs owner"},
    ])
    _make_review_dir(tmp_path, monkeypatch)
    return root


def test_gather_reads_all_sources_and_keeps_shape(tmp_path, monkeypatch):
    root = _seed_happy_run(tmp_path, monkeypatch)

    snap = run_watch.gather(str(root), WI)

    assert snap["work_item"] == WI
    assert snap["phase"]["value"] == "review-code"
    assert snap["phase"]["step"] == 6
    assert snap["phase"]["total"] == 10
    assert snap["gates"] == {"review": "passed", "test": "pending"}
    assert snap["review"]["round"] == 2
    assert snap["review"]["terminal"] == "unclean"
    assert snap["review"]["dimensions"]["security"]["blocking_count"] == 1
    assert snap["review"]["dimensions"]["security"]["finding_titles"] == ["buffer-overflow"]
    assert snap["build"]["reviewed"] == 2
    assert snap["build"]["built"] == 1
    assert snap["build"]["total"] == 3
    assert snap["run"]["state"] == "parked"
    assert snap["run"]["last_park"] == "needs owner"
    assert snap["events"][-1]["type"] == "parked"


def test_gather_uses_journal_phase_for_suffixed_review_code_dirs(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    _make_tasks_doc(root, WI, count=1)
    paths = control_plane.paths(str(root), WI)
    _write_json(paths["checkpoint"], {
        "schemaVersion": 2,
        "workItem": WI,
        "phase": "test-pilot",
        "gates": {"review": "passed"},
        "lastGoodStep": 6,
        "lastGoodPhase": "draft-PR",
        "updatedAt": "2026-07-03T14:39:00Z",
    })
    _write_events(paths["events"], [
        {"ts": "2026-07-03T14:40:00Z", "seq": 1, "type": "phase_record",
         "payload": {"phase": "test-pilot", "confidence": "low"}},
    ])
    _make_review_dir(tmp_path, monkeypatch, phase="review-code-test-pilot-1-head")

    snap = run_watch.gather(str(root), WI)

    assert snap["phase"]["value"] == "test-pilot"
    assert snap["review"]["available"] is True
    assert "showrunner-live-watch-152-review-code-test-pilot-1-head" in snap["review"]["run_dir"]
    assert snap["review"]["dimensions"]["security"]["blocking_count"] == 1


def test_gather_reports_lease_state_when_store_has_lease(tmp_path, monkeypatch):
    root = _seed_happy_run(tmp_path, monkeypatch)
    store = control_plane.ensure_store(str(root))
    ref_lock._force_lease(store, WI, {
        "pid": os.getpid(),
        "host": ref_lock._host(),
        "bootId": hostinfo.boot_id(),
        "acquiredAt": ref_lock._stamp(),
        "generation": 1,
        "ttl": ref_lock.DEFAULT_TTL,
    })

    snap = run_watch.gather(str(root), WI)

    assert snap["run"]["state"] == "active"
    assert snap["run"]["detail"] == "lease held, fresh"
    assert snap["run"]["holder"].endswith(":%s" % os.getpid())

    ref_lock._force_lease(store, WI, {
        "pid": 999999,
        "host": ref_lock._host(),
        "bootId": hostinfo.boot_id(),
        "acquiredAt": "1970-01-01T00:00:00Z",
        "generation": 2,
        "ttl": 1,
    })

    stale = run_watch.gather(str(root), WI)

    assert stale["run"]["state"] == "stale"
    assert stale["run"]["detail"] == "lease held, stale"


def test_gather_degrades_each_bad_source_without_crashing(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.setattr(run_watch, "REVIEW_ROOT", str(tmp_path / "review-root"))
    paths = control_plane.paths(str(root), WI)
    os.makedirs(paths["issue_dir"], exist_ok=True)
    with open(paths["checkpoint"], "w", encoding="utf-8") as fh:
        fh.write("{nope")
    with open(os.path.join(paths["issue_dir"], "build-state.json"), "w", encoding="utf-8") as fh:
        fh.write("[")
    bad_review_dir = tmp_path / "review-root" / f"showrunner-{WI}-unknown"
    bad_review_dir.mkdir(parents=True)
    (bad_review_dir / "round-records.json").write_text("[", encoding="utf-8")

    snap = run_watch.gather(str(root), WI)

    assert snap["phase"]["value"] == "unknown"
    assert snap["review"]["available"] is False
    assert snap["build"]["available"] is True
    assert snap["build"]["reviewed"] == 0
    assert snap["run"]["state"] == "unknown"


def test_render_snapshot_formats_representative_and_absent_lines():
    snap = {
        "work_item": WI,
        "phase": {"value": "review-code", "step": 6, "total": 10},
        "gates": {"review": "passed", "test": "pending"},
        "review": {
            "available": True,
            "round": 2,
            "terminal": "unclean",
            "dimensions": {
                "code": {"status": "clean", "blocking_count": 0, "finding_titles": []},
                "security": {"status": "findings", "blocking_count": 1, "finding_titles": ["buffer-overflow"]},
                "architecture": {"status": "clean", "blocking_count": 0, "finding_titles": []},
            },
        },
        "build": {"available": True, "reviewed": 2, "built": 1, "total": 3, "final_review": {"clean": False}},
        "run": {"state": "active", "detail": "from events", "last_park": None},
        "updated": "12s ago",
    }
    text = run_watch.render_snapshot(snap)

    assert text.splitlines()[0] == "showrunner · live-watch-152"
    assert "phase   review-code  (step 6/10)     gates  review ✓  test –" in text
    assert "review  round 2    code ✓ · security ✗(1 blocking) · architecture ✓   → unclean" in text
    assert "build   tasks 2/3 reviewed · 1/3 built     final-review dirty" in text
    assert "run     active (from events)         last park  —" in text
    assert "updated 12s ago" in text

    absent = dict(snap)
    absent["review"] = {"available": False}
    assert "review  — (no review yet)" in run_watch.render_snapshot(absent)


def test_diff_reports_review_and_build_facts_that_journal_does_not_carry():
    prev = {
        "clock": "14:35:12",
        "phase": {"value": "review-code"},
        "review": {
            "available": True,
            "round": 1,
            "terminal": None,
            "dimensions": {"security": {"status": "clean", "blocking_count": 0, "finding_titles": []}},
        },
        "build": {"available": True, "reviewed": 1, "built": 0, "total": 3},
    }
    curr = {
        "clock": "14:36:05",
        "phase": {"value": "review-code"},
        "review": {
            "available": True,
            "round": 2,
            "terminal": "unclean",
            "dimensions": {
                "security": {
                    "status": "findings",
                    "blocking_count": 1,
                    "finding_titles": ["buffer-overflow"],
                }
            },
        },
        "build": {"available": True, "reviewed": 2, "built": 1, "total": 3},
    }

    assert run_watch.diff(prev, curr) == [
        "14:36:05  → review-code round 2 started",
        "14:36:05  · round 2 security ✗ 1 blocking (buffer-overflow)",
        "14:36:05  → round 2 verdict: unclean",
        "14:36:05  · build task 2/3 reviewed",
        "14:36:05  · build task 1/3 built",
    ]


def test_diff_reports_same_count_blockers_when_round_or_titles_change():
    prev = {
        "clock": "14:35:12",
        "phase": {"value": "review-code"},
        "review": {
            "available": True,
            "round": 1,
            "terminal": None,
            "dimensions": {"security": {
                "status": "findings",
                "blocking_count": 1,
                "finding_titles": ["old-blocker"],
            }},
        },
        "build": {"available": True, "reviewed": 1, "built": 0, "total": 3},
    }
    curr = {
        "clock": "14:36:05",
        "phase": {"value": "review-code"},
        "review": {
            "available": True,
            "round": 2,
            "terminal": None,
            "dimensions": {"security": {
                "status": "findings",
                "blocking_count": 1,
                "finding_titles": ["new-blocker"],
            }},
        },
        "build": {"available": True, "reviewed": 1, "built": 0, "total": 3},
    }

    assert run_watch.diff(prev, curr) == [
        "14:36:05  → review-code round 2 started",
        "14:36:05  · round 2 security ✗ 1 blocking (new-blocker)",
    ]


def test_format_journal_event_interesting_types():
    assert run_watch.format_journal_event({
        "ts": "2026-07-03T14:32:01Z",
        "type": "run_started",
        "detail": WI,
    }) == "14:32:01  ▶ run started · live-watch-152"
    assert run_watch.format_journal_event({
        "ts": "2026-07-03T14:35:12Z",
        "type": "step_entered",
        "step": "review-code",
    }) == "14:35:12  → review-code"
    assert run_watch.format_journal_event({
        "ts": "2026-07-03T14:38:30Z",
        "type": "gate",
        "step": "review-code",
        "detail": "passed",
    }) == "14:38:30  ✓ review-code gate passed"
    assert run_watch.format_journal_event({
        "ts": "2026-07-03T14:43:22Z",
        "type": "run_completed",
    }) == "14:43:22  ✓ run completed"
    # #25: the quick route's skipped front-half phases surface in the live readout, never silently.
    assert run_watch.format_journal_event({
        "ts": "2026-07-03T14:30:00Z",
        "type": "phases_skipped",
        "payload": {"route": "quick", "skipped": ["plan", "review-plan", "tasks", "review-tasks"]},
    }) == "14:30:00  ⏭ quick route — skipped plan, review-plan, tasks, review-tasks"
    # a bare-detail park still renders its detail suffix (unchanged).
    assert run_watch.format_journal_event({
        "ts": "2026-07-03T14:44:00Z", "type": "parked", "detail": "needs owner",
    }) == "14:44:00  ‼ parked · needs owner"
    # #446: a park that folded a structured payload names its cause from payload.reason (no mute park).
    assert run_watch.format_journal_event({
        "ts": "2026-07-03T14:45:00Z", "type": "parked",
        "payload": {"reason": "phase recorded a material assumption: ledger unreadable",
                    "assumptions": ["ledger unreadable"]},
    }) == "14:45:00  ‼ parked · phase recorded a material assumption: ledger unreadable"


def test_phases_skipped_counts_as_active_state(tmp_path):
    # #25: a run observed right at intake (its last event is phases_skipped) reads as active, not
    # unknown — the skip record is part of a live run, not a terminal marker. No lease store under
    # tmp_path, so _read_run falls through to the event-type classification.
    got = run_watch._read_run(str(tmp_path), "wi", [
        {"seq": 1, "type": "phases_skipped",
         "payload": {"route": "quick", "skipped": ["plan"]}},
    ])
    assert got["state"] == "active"


def test_watch_command_resolves_absolute_paths_and_quotes(tmp_path):
    lib_dir = tmp_path / "lib dir"
    root = tmp_path / "repo dir"
    lib_dir.mkdir()
    root.mkdir()

    assert run_watch.watch_command(str(lib_dir), str(root), WI) == (
        f'python3 "{lib_dir / "run_watch.py"}" --work-item live-watch-152 '
        f'--root "{root}" --follow'
    )


def test_watch_command_shell_quotes_expansion_characters(tmp_path):
    lib_dir = tmp_path / "lib$HOME"
    root = tmp_path / "repo$(echo bad)"
    lib_dir.mkdir()
    root.mkdir()

    command = run_watch.watch_command(str(lib_dir), str(root), "wi $(bad)")

    assert "'%s'" % (lib_dir / "run_watch.py") in command
    assert "'%s'" % root in command
    assert "'wi $(bad)'" in command


def test_watch_command_quotes_shell_metacharacters_in_work_item(tmp_path):
    lib_dir = tmp_path / "lib"
    root = tmp_path / "repo"
    lib_dir.mkdir()
    root.mkdir()

    command = run_watch.watch_command(str(lib_dir), str(root), "wi;bad")

    assert "'wi;bad'" in command


def test_gather_survives_non_dict_events_line(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.setattr(run_watch, "REVIEW_ROOT", str(tmp_path / "review-root"))
    paths = control_plane.paths(str(root), WI)
    os.makedirs(paths["issue_dir"], exist_ok=True)
    with open(paths["events"], "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"ts": "2026-07-03T14:32:01Z", "seq": 1, "type": "run_started"}) + "\n")
        fh.write("5\n")                          # valid JSON, not an object
        fh.write(json.dumps([1, 2, 3]) + "\n")   # valid JSON array, not an object
        fh.write(json.dumps({"ts": "2026-07-03T14:37:00Z", "seq": 2,
                             "type": "parked", "detail": "why"}) + "\n")

    snap = run_watch.gather(str(root), WI)       # must not raise

    assert [e["type"] for e in snap["events"]] == ["run_started", "parked"]
    assert snap["run"]["state"] == "parked"
    assert snap["run"]["last_park"] == "why"
    assert isinstance(run_watch.render_snapshot(snap), str)


def test_gather_degrades_on_valid_json_wrong_types(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    review_root = tmp_path / "review-root"
    monkeypatch.setattr(run_watch, "REVIEW_ROOT", str(review_root))
    paths = control_plane.paths(str(root), WI)
    os.makedirs(paths["issue_dir"], exist_ok=True)
    _write_json(paths["checkpoint"], [])                                   # list, not object
    _write_json(os.path.join(paths["issue_dir"], "build-state.json"), [])  # list, not object
    run_dir = review_root / f"showrunner-{WI}-review-code"
    run_dir.mkdir(parents=True)
    _write_json(run_dir / "round-records.json", {})                        # object, not list

    snap = run_watch.gather(str(root), WI)

    assert snap["phase"]["value"] == "unknown"
    assert snap["review"]["available"] is False
    assert snap["build"]["available"] is True
    assert snap["build"]["reviewed"] == 0
    assert isinstance(run_watch.render_snapshot(snap), str)


def test_render_skipped_dimension_shows_dash_not_check():
    snap = {
        "work_item": WI,
        "phase": {"value": "review-code", "step": 6, "total": 10},
        "gates": {},
        "review": {"available": True, "round": 2, "terminal": None, "dimensions": {
            "premortem": {"status": "skipped", "blocking_count": 0, "finding_titles": []},
            "code": {"status": "clean", "blocking_count": 0, "finding_titles": []},
        }},
        "build": {"available": False},
        "run": {"state": "active"},
        "updated": "1s ago",
    }
    text = run_watch.render_snapshot(snap)

    assert "premortem –" in text
    assert "premortem ✓" not in text
    assert "code ✓" in text


def test_dimension_snapshot_skipped_but_carried_blocking_shows_blocking():
    dim = {"status": "skipped", "blocking_count": 1, "finding_titles": ["carried"]}
    assert run_watch._dimension_snapshot("security", dim) == "security ✗(1 blocking)"


def test_gather_blocking_count_is_recomputed_from_severities(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    _make_tasks_doc(root, WI, count=1)
    review_root = tmp_path / "review-root"
    monkeypatch.setattr(run_watch, "REVIEW_ROOT", str(review_root))
    paths = control_plane.paths(str(root), WI)
    _write_json(paths["checkpoint"], {
        "schemaVersion": 2, "workItem": WI, "phase": "review-code",
        "lastGoodStep": 5, "lastGoodPhase": "review-code",
        "updatedAt": "2026-07-03T14:39:00Z", "gates": {},
    })
    run_dir = review_root / f"showrunner-{WI}-review-code"
    run_dir.mkdir(parents=True)
    _write_json(run_dir / "round-records.json", [{
        "schemaVersion": 2, "round": 1, "dimensions": {"security": {
            "status": "findings",
            "blockingCount": 5,   # deliberately WRONG; must be ignored in favour of recompute
            "findings": [
                {"title": "buffer-overflow", "severity": "Important"},
                {"taxonomy": "style", "severity": "Minor"},   # no title -> falls back to taxonomy
            ],
        }},
    }])

    snap = run_watch.gather(str(root), WI)
    sec = snap["review"]["dimensions"]["security"]

    assert sec["blocking_count"] == 1                  # recomputed: only the Important finding
    assert "buffer-overflow" in sec["finding_titles"]
    assert "style" in sec["finding_titles"]            # title fell back to taxonomy


def test_diff_detects_intra_round_blocker_and_verdict_without_round_change():
    prev = {"clock": "14:35:00", "phase": {"value": "review-code"},
            "review": {"available": True, "round": 2, "terminal": None,
                       "dimensions": {"security": {"status": "clean", "blocking_count": 0,
                                                   "finding_titles": []}}},
            "build": {"available": False}}
    curr = {"clock": "14:36:00", "phase": {"value": "review-code"},
            "review": {"available": True, "round": 2, "terminal": "unclean",
                       "dimensions": {"security": {"status": "findings", "blocking_count": 1,
                                                   "finding_titles": ["boom"]}}},
            "build": {"available": False}}

    lines = run_watch.diff(prev, curr)

    assert "14:36:00  · round 2 security ✗ 1 blocking (boom)" in lines
    assert "14:36:00  → round 2 verdict: unclean" in lines
    assert not any("started" in ln for ln in lines)   # round unchanged -> no "round started"


def test_poll_lines_no_duplicate_and_no_drop_across_polls():
    def ev(seq, typ, **k):
        return dict(ts="2026-07-03T14:%02d:00Z" % seq, seq=seq, type=typ, **k)

    base = {"review": {"available": False}, "build": {"available": False},
            "phase": {"value": "workhorse"}}
    prev = dict(base, events=[ev(1, "run_started"), ev(2, "step_entered", step="workhorse")])
    curr = dict(base, events=prev["events"] + [ev(3, "parked", detail="x"), ev(4, "resumed")])

    lines, seen = run_watch._poll_lines(prev, curr, 2)

    assert seen == 4
    assert sum("parked" in ln for ln in lines) == 1
    assert sum("resumed" in ln for ln in lines) == 1
    assert not any("run started" in ln for ln in lines)   # seq 1 already seen -> not replayed

    lines2, seen2 = run_watch._poll_lines(curr, curr, seen)

    assert lines2 == []                                    # nothing new -> no output
    assert seen2 == 4


def test_format_journal_event_numeric_and_named_steps():
    assert run_watch.format_journal_event(
        {"ts": "2026-07-03T14:35:12Z", "type": "step_entered", "step": 1}) == "14:35:12  → step 1"
    assert run_watch.format_journal_event(
        {"ts": "2026-07-03T14:36:12Z", "type": "step_completed", "step": 2}) == "14:36:12  ✓ step 2"
    assert run_watch.format_journal_event(
        {"ts": "2026-07-03T14:37:12Z", "type": "step_entered", "step": "review-code"}) == "14:37:12  → review-code"


def test_review_from_prior_phase_is_annotated(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    review_root = tmp_path / "review-root"
    monkeypatch.setattr(run_watch, "REVIEW_ROOT", str(review_root))
    paths = control_plane.paths(str(root), WI)
    _write_json(paths["checkpoint"], {
        "schemaVersion": 2, "workItem": WI, "phase": "test-pilot",
        "lastGoodStep": 7, "lastGoodPhase": "test-pilot",
        "updatedAt": "2026-07-03T14:39:00Z", "gates": {},
    })
    # only a stale review-plan dir exists while the current phase is test-pilot
    run_dir = review_root / f"showrunner-{WI}-review-plan"
    run_dir.mkdir(parents=True)
    _write_json(run_dir / "round-records.json", [
        {"schemaVersion": 2, "round": 1, "dimensions": {"code": {"status": "clean"}}}])
    _write_json(run_dir / "terminal-record.json", {"terminal": "clean", "round": 1})

    snap = run_watch.gather(str(root), WI)

    assert snap["review"]["from_phase"] == "review-plan"
    assert "(from review-plan)" in run_watch.render_snapshot(snap)


def test_poll_lines_includes_diff_content_after_new_event():
    prev = {"events": [{"ts": "2026-07-03T14:00:00Z", "seq": 1, "type": "run_started"}],
            "review": {"available": False},
            "build": {"available": True, "reviewed": 1, "built": 0, "total": 3},
            "phase": {"value": "workhorse"}}
    curr = {"events": prev["events"] + [{"ts": "2026-07-03T14:01:00Z", "seq": 2, "type": "step_completed", "step": 5}],
            "review": {"available": False},
            "build": {"available": True, "reviewed": 1, "built": 1, "total": 3},
            "phase": {"value": "workhorse"}}
    lines, seen = run_watch._poll_lines(prev, curr, 1)
    assert seen == 2
    assert any("step 5" in ln for ln in lines)
    assert any("build task 1/3 built" in ln for ln in lines)
    event_idx = next(i for i, ln in enumerate(lines) if "step 5" in ln)
    diff_idx = next(i for i, ln in enumerate(lines) if "build task 1/3 built" in ln)
    assert event_idx < diff_idx


def test_format_journal_event_coerces_non_string_type():
    # a corrupt on-disk event with a non-string `type` must not crash --follow
    for bad_type in (5, ["x"], {"k": 1}, "", None):
        line = run_watch.format_journal_event(
            {"ts": "2026-07-03T14:00:00Z", "seq": 1, "type": bad_type})
        assert line == "14:00:00  · event"
    # with a detail, the coerced line still renders the detail suffix
    assert run_watch.format_journal_event(
        {"ts": "2026-07-03T14:00:00Z", "seq": 1, "type": 5, "detail": "bad"}) == "14:00:00  · event · bad"
