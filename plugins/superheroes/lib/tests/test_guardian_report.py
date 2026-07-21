import guardian_report as gr
import guardian_sweep as gsw
from guardian_fixtures import FixtureLens, init_calibrated_repo, write_guardian_layer


def _sample_bundle():
    return {
        "committed": "uncommitted",
        "storageMode": "in-repo",
        "surfaced": [{"id": "a", "lens": "fixture"}],
        "ledgerStatus": [{"id": "b", "lens": "fixture", "line": "filed as #9, verification pending"}],
        "vitalsDelta": {},
        "reportCard": {},
        "funnel": {
            "raised": {"fixture": 2},
            "killedByDrift": [{"id": "c", "lens": "fixture", "reason": "no-drift"}],
            "killedByLedger": [{"id": "d", "lens": "fixture", "disposition": "accepted"}],
            "degradedLenses": [],
        },
    }


def _sample_dispositions():
    return [
        {
            "id": "a",
            "verdict": "validated",
            "consequence": "Refactor the module.",
            "receipt": "complexity=120",
            "effort": "2 days",
            "ledgerJoin": "a",
        },
        {"id": "x", "verdict": "rejected"},
    ]


def test_render_contains_standing_instructions():
    md = gr.render(_sample_bundle(), [], {"byId": {}})
    assert gr.HEADER_STANDING_INSTRUCTIONS in md
    assert "Verify each finding against its receipt" in md


def test_render_validated_finding_fields():
    md = gr.render(_sample_bundle(), _sample_dispositions(), {"byId": {}})
    assert gr.HEADER_VALIDATED in md
    assert "Refactor the module." in md
    assert "complexity=120" in md
    assert "2 days" in md


def test_render_filed_status_line():
    md = gr.render(_sample_bundle(), [], {"byId": {}})
    assert gr.HEADER_TRACKED in md
    assert "filed as #9, verification pending" in md


def test_render_vitals_section():
    md = gr.render(_sample_bundle(), [], {"byId": {}})
    assert gr.HEADER_VITALS in md


def test_render_funnel_buckets_use_constants():
    md = gr.render(_sample_bundle(), _sample_dispositions(), {"byId": {}})
    assert gr.HEADER_FUNNEL in md
    assert gr.FUNNEL_RAISED in md
    assert gr.FUNNEL_MALFORMED in md
    assert gr.FUNNEL_KILLED_DRIFT in md
    assert gr.FUNNEL_KILLED_LEDGER in md
    assert gr.FUNNEL_DEGRADED in md
    assert gr.FUNNEL_REJECTED in md
    assert gr.FUNNEL_VALIDATED in md
    assert "fixture: 2" in md
    assert "no-drift" in md
    assert "accepted" in md


def test_render_ledger_history_for_validated_join():
    bundle = _sample_bundle()
    dispositions = _sample_dispositions()
    ledger = {
        "byId": {
            "a": {"id": "a", "disposition": "accepted", "issue": None},
        },
    }
    md = gr.render(bundle, dispositions, ledger)
    assert "**Ledger history:**" in md
    assert "disposition=accepted" in md


def test_render_header_in_repo_states_mode_and_pr_consequence():
    bundle = _sample_bundle()
    bundle["storageMode"] = "in-repo"
    bundle["committed"] = "uncommitted"
    md = gr.render(bundle, [], {"byId": {}})
    assert "storage: in-repo" in md
    assert "durability requires a PR" in md
    assert "committed: uncommitted" not in md


def test_render_header_global_states_machine_local():
    bundle = _sample_bundle()
    bundle["storageMode"] = "global"
    bundle["committed"] = "machine-local"
    md = gr.render(bundle, [], {"byId": {}})
    assert "storage: global" in md
    assert "machine-local" in md


def test_render_vitals_crossings_like_findings():
    bundle = _sample_bundle()
    bundle["vitalsDelta"] = {
        "crossings": [{
            "vital": "todoCount",
            "prev": 4,
            "cur": 8,
            "change": 4,
            "pct": 1.0,
            "sentence": (
                "TODO/FIXME markers grew from 4 to 8 (4 more) since the last sweep"),
        }],
        "delta": {
            "todoCount": {"prev": 4, "cur": 8, "change": 4, "pct": 1.0},
            "fileCount": {"prev": 10, "cur": 11, "change": 1, "pct": 0.1},
        },
    }
    md = gr.render(bundle, [], {"byId": {}})
    assert "TODO/FIXME markers grew from 4 to 8" in md
    assert "Other movement:" in md
    assert "fileCount: 10 → 11" in md
    assert "critical" not in md.lower()
    assert "severity" not in md.lower()


def test_render_vitals_measured_no_movement():
    bundle = _sample_bundle()
    bundle["vitalsDelta"] = {
        "crossings": [],
        "delta": {},
        "notCollected": {},
    }
    md = gr.render(bundle, [], {"byId": {}})
    assert "_No vitals movement._" in md
    assert "turned off" not in md.lower()
    assert "Not collected:" not in md


def test_render_vitals_disabled_via_real_collect(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    store = str(tmp_path / "store")
    write_guardian_layer(tmp_path, {"vitals": False})
    bundle = gsw.collect(cwd=repo, lenses=[FixtureLens()], root=store)
    assert bundle["vitalsDelta"] == {}

    md = gr.render(bundle, [], {"byId": {}})
    assert "Vitals collection is turned off for this project" in md
    assert "no trend this sweep" in md
    assert "_No vitals movement._" not in md


def test_render_vitals_not_collected_shows_reasons_not_stable_empty():
    bundle = _sample_bundle()
    bundle["vitalsDelta"] = {
        "crossings": [],
        "delta": {},
        "notCollected": {
            "suiteTestCount": "verify suite produced no parseable summary",
            "todoCount": "git unavailable",
        },
    }
    md = gr.render(bundle, [], {"byId": {}})
    assert "Not collected:" in md
    assert "suiteTestCount: verify suite produced no parseable summary" in md
    assert "todoCount: git unavailable" in md
    assert "_No vitals movement — nothing was collected this sweep._" in md
    assert md.count("_No vitals movement._") == 0


def test_render_vitals_not_collected_alongside_movement():
    bundle = _sample_bundle()
    bundle["vitalsDelta"] = {
        "crossings": [],
        "delta": {
            "fileCount": {"prev": 10, "cur": 11, "change": 1, "pct": 0.1},
        },
        "notCollected": {
            "suiteTestCount": "verify suite produced no parseable summary",
        },
    }
    md = gr.render(bundle, [], {"byId": {}})
    assert "fileCount: 10 → 11" in md
    assert "Not collected:" in md
    assert "suiteTestCount: verify suite produced no parseable summary" in md
    assert "nothing was collected" not in md


def test_render_report_card_benched_and_below_floor():
    bundle = _sample_bundle()
    bundle["reportCard"] = {
        "dup": {
            "adjudicated": 10, "for": 1, "against": 9,
            "actionability": 0.1, "sweeps": 3, "benched": True,
            "reason": "dup is benched: only 10% of its 10 adjudicated findings were useful, "
                      "under the 90% bar across 3 sweeps — it collects silently until its "
                      "validation rules are tuned.",
        },
        "hotspot": {
            "adjudicated": 2, "for": 2, "against": 0,
            "actionability": 1.0, "sweeps": 1, "benched": False,
            "reason": "hotspot has 2 of the 10 adjudicated findings the bar needs before "
                      "it can bench a lens — still gathering evidence.",
        },
    }
    md = gr.render(bundle, [], {"byId": {}})
    assert gr.HEADER_REPORT_CARD in md
    assert "dup is benched" in md
    assert "still gathering evidence" in md
    assert "hotspot is active" not in md
