"""Skew disclosure union, disposition census, and doc-drift pins (issue #1107 WO-D)."""
import importlib.util
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_HERE, "..")
_PLUGIN_ROOT = os.path.join(_LIB, "..")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import round_driver as RD
import version_skew


def _load_version_skew():
    spec = importlib.util.spec_from_file_location(
        "version_skew_isolated",
        os.path.join(_LIB, "version_skew.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _skew_record(detail, reason="plugin-version-skew: test", inspected_root="/tmp/repo"):
    return {
        "constraint": version_skew.CONSTRAINT,
        "status": version_skew.STATUS_CHECKED_DEGRADED,
        "detail": detail,
        "reason": reason,
        "inspectedRoot": inspected_root,
    }


def _seat_map_with_skew_records(*records):
    from test_round_driver import _seat_map_vendors

    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    seat_map["degradations"] = list(records)
    seat_map["pluginVersionSkew"] = {
        "status": version_skew.STATUS_CHECKED_DEGRADED,
        "detail": records[0]["detail"] if records else version_skew.DETAIL_SEMANTICS_DIVERGENT,
        "inspectedRoot": records[0].get("inspectedRoot", "/tmp/repo") if records else "",
    }
    return seat_map


def _fold_panel_skew(state, seat_map):
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    RD._fold_panel(state, state["config"], {"seats": seats, "seatMap": seat_map})


# --- Part 1: skew disclosure channel union ---


def test_no_skew_record_channel_absent_from_receipt():
    from test_round_driver import _cfg, _seat_map_vendors

    state = RD.new_state(_cfg(leg="panel", vendors=["codex", "cursor"]))
    seat_map = _seat_map_vendors({d: "claude" for d in RD.DIMENSIONS})
    _fold_panel_skew(state, seat_map)
    assert RD._skew_records(state) == []
    receipt = RD.build_receipt(state)
    r1 = next((r for r in receipt["rounds"] if r["round"] == 1), None)
    if r1 is not None:
        assert "pluginVersionSkew" not in r1


def test_one_skew_record_submitted_once_present():
    from test_round_driver import _cfg

    rec = _skew_record(version_skew.DETAIL_SEMANTICS_DIVERGENT, reason="alpha reason")
    state = RD.new_state(_cfg(leg="panel", vendors=["codex", "cursor"]))
    _fold_panel_skew(state, _seat_map_with_skew_records(rec))
    records = RD._skew_records(state)
    assert len(records) == 1
    assert records[0]["reason"] == "alpha reason"


def test_two_skew_records_differing_only_in_detail_both_present():
    from test_round_driver import _cfg

    rec_a = _skew_record("detail-alpha", reason="alpha")
    rec_b = _skew_record("detail-beta", reason="beta")
    state = RD.new_state(_cfg(leg="panel", vendors=["codex", "cursor"]))
    seat_map = _seat_map_with_skew_records(rec_a, rec_b)
    _fold_panel_skew(state, seat_map)
    records = RD._skew_records(state)
    details = {r["detail"] for r in records}
    assert details == {"detail-alpha", "detail-beta"}


def test_same_skew_record_submitted_twice_deduped():
    from test_round_driver import _cfg

    rec = _skew_record(version_skew.DETAIL_SEMANTICS_DIVERGENT, reason="once")
    state = RD.new_state(_cfg(leg="panel", vendors=["codex", "cursor"]))
    seat_map = _seat_map_with_skew_records(rec)
    _fold_panel_skew(state, seat_map)
    _fold_panel_skew(state, seat_map)
    records = RD._skew_records(state)
    assert len(records) == 1


def test_later_same_round_submission_unions_not_replaces():
    from test_round_driver import _cfg

    rec_a = _skew_record("detail-alpha", reason="first submission")
    rec_b = _skew_record("detail-beta", reason="second submission")
    state = RD.new_state(_cfg(leg="panel", vendors=["codex", "cursor"]))
    _fold_panel_skew(state, _seat_map_with_skew_records(rec_a))
    _fold_panel_skew(state, _seat_map_with_skew_records(rec_b))
    records = RD._skew_records(state)
    details = {r["detail"] for r in records}
    assert details == {"detail-alpha", "detail-beta"}


def test_records_path_resume_restores_skew_disclosures(tmp_path):
    from test_round_driver import _cfg

    rec = _skew_record(version_skew.DETAIL_SEMANTICS_DIVERGENT, reason="resumed skew")
    records = tmp_path / "round-records.json"
    records.write_text(json.dumps([{
        "schemaVersion": 2,
        "round": 1,
        "kind": "baseline",
        "dimensions": {"test-reviewer": {"status": "run", "confidence": "high",
                                          "tier": "reviewer-deep", "findings": []}},
        "findings": [],
        "coverageDecisions": [],
        "disclosures": {"pluginVersionSkew": [rec]},
    }]))
    state = RD.new_state(_cfg(leg="panel", recordsPath=str(records)))
    records_out = RD._skew_records(state)
    assert len(records_out) == 1
    assert records_out[0]["reason"] == "resumed skew"


def test_malformed_skew_record_skipped_not_crashing():
    state = {
        "rounds": {
            "1": {
                "pluginVersionSkew": [
                    None,
                    42,
                    {"status": version_skew.STATUS_CHECKED_DEGRADED},
                    {"constraint": version_skew.CONSTRAINT, "status": ["unhashable"]},
                    _skew_record(version_skew.DETAIL_SEMANTICS_DIVERGENT),
                ],
            },
        },
        "seatMap": {},
    }
    records = RD._skew_records(state)
    assert len(records) == 2
    assert any(r.get("status") == ["unhashable"] for r in records)
    assert any(r.get("status") == version_skew.STATUS_CHECKED_DEGRADED for r in records)
    receipt = RD.build_receipt(
        {**state, "config": {}, "findings": [], "decisions": [], "certification": {}},
    )
    assert isinstance(receipt, dict)


def test_invalid_skew_status_disclosed_as_degrading():
    # axis: unknown skew status fails closed at every consumer — same disposition as appends_degradation
    bogus = {
        "constraint": version_skew.CONSTRAINT,
        "status": "bogus-status",
        "detail": version_skew.DETAIL_SEMANTICS_DIVERGENT,
        "reason": "future seat-map token",
        "inspectedRoot": "/tmp/repo",
    }
    state = {
        "rounds": {"1": {"pluginVersionSkew": [bogus]}},
        "seatMap": {"degradations": [bogus]},
    }
    records = RD._skew_records(state)
    assert len(records) == 1
    assert records[0]["status"] == "bogus-status"
    assert RD._skew_degraded(state) is True


# --- Part 2: disposition census and appends_degradation ---


def test_every_status_member_has_disposition():
    for status in version_skew.STATUSES:
        assert status in version_skew.STATUS_DISPOSITIONS, (
            "undispositioned STATUSES member: %r" % status
        )


def test_appends_degradation_known_members():
    assert version_skew.appends_degradation(version_skew.STATUS_CHECKED_DEGRADED) is True
    assert version_skew.appends_degradation(version_skew.STATUS_CHECKED_CLEAN) is False
    assert version_skew.appends_degradation(version_skew.STATUS_NOT_CHECKED) is False


def test_appends_degradation_unknown_status_fails_closed():
    assert version_skew.appends_degradation("future-status") is True
    assert version_skew.appends_degradation(None) is True
    assert version_skew.appends_degradation(["unhashable"]) is True


def test_containment_refusal_manifest_symlink_evidence_unreadable(tmp_path):
    VS = _load_version_skew()
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    real_manifest = tmp_path / "real-plugin.json"
    real_manifest.write_text(
        json.dumps({"name": "superheroes", "version": "0.30.0"}), encoding="utf-8",
    )
    manifest_dir = repo / "plugins" / "superheroes" / ".claude-plugin"
    manifest_dir.mkdir(parents=True)
    os.symlink(real_manifest, manifest_dir / "plugin.json")
    plugin = tmp_path / "plugin"
    manifest = plugin / ".claude-plugin" / "plugin.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"name": "superheroes", "version": "0.29.0"}), encoding="utf-8")
    lib = plugin / "lib"
    lib.mkdir(parents=True)
    for entry in VS.SEMANTICS_FILES:
        src = os.path.join(_PLUGIN_ROOT, entry)
        (lib / os.path.basename(entry)).write_text(open(src, encoding="utf-8").read(), encoding="utf-8")
    record = VS.detect(str(repo), str(plugin))
    assert record["status"] == VS.STATUS_CHECKED_DEGRADED
    assert record["detail"] == VS.DETAIL_EVIDENCE_UNREADABLE


def _read_plugin_doc(rel):
    path = os.path.join(_PLUGIN_ROOT, rel)
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def test_plugin_version_skew_status_vocabulary_round_driver_doc():
    doc = _read_plugin_doc("skills/review-code/reference/round-driver.md")
    missing = sorted(token for token in version_skew.STATUSES if token not in doc)
    assert not missing, (
        "round-driver.md missing plugin-version-skew status token(s) from "
        "version_skew.STATUSES: %r" % missing
    )


def test_plugin_version_skew_status_vocabulary_setup_doc():
    doc = _read_plugin_doc("skills/review-code/reference/setup.md")
    missing = sorted(token for token in version_skew.STATUSES if token not in doc)
    assert not missing, (
        "setup.md missing plugin-version-skew status token(s) from "
        "version_skew.STATUSES: %r" % missing
    )


# --- Part 3: plugin.json-only repo version ---


def _write_manifest(base, version="0.30.0", name="superheroes"):
    path = base / "plugins" / "superheroes" / ".claude-plugin" / "plugin.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"name": name, "version": version}), encoding="utf-8")


def _copy_semantics_to(base):
    lib = base / "plugins" / "superheroes" / "lib"
    lib.mkdir(parents=True, exist_ok=True)
    for entry in version_skew.SEMANTICS_FILES:
        src = os.path.join(_PLUGIN_ROOT, entry)
        (lib / os.path.basename(entry)).write_text(open(src, encoding="utf-8").read(), encoding="utf-8")


def _plugin_tree(tmp_path, version="0.29.0"):
    root = tmp_path / "plugin"
    manifest = root / ".claude-plugin" / "plugin.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps({"name": "superheroes", "version": version}), encoding="utf-8")
    lib = root / "lib"
    lib.mkdir(parents=True, exist_ok=True)
    for entry in version_skew.SEMANTICS_FILES:
        src = os.path.join(_PLUGIN_ROOT, entry)
        (lib / os.path.basename(entry)).write_text(open(src, encoding="utf-8").read(), encoding="utf-8")
    return str(root)


def test_repo_version_from_plugin_json_not_version_txt(tmp_path):
    repo = tmp_path / "repo"
    _write_manifest(repo, version="0.30.0")
    _copy_semantics_to(repo)
    version_txt = repo / "plugins" / "superheroes" / "version.txt"
    version_txt.write_text("9.99.9\n", encoding="utf-8")
    plugin = _plugin_tree(tmp_path)
    record = version_skew.detect(str(repo), plugin)
    assert record["status"] == version_skew.STATUS_CHECKED_CLEAN
    assert "0.30.0" in record["reason"]
    assert "9.99.9" not in record["reason"]


def test_repo_version_missing_version_field_unknown(tmp_path):
    repo = tmp_path / "repo"
    path = repo / "plugins" / "superheroes" / ".claude-plugin" / "plugin.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"name": "superheroes"}), encoding="utf-8")
    _copy_semantics_to(repo)
    plugin = _plugin_tree(tmp_path)
    record = version_skew.detect(str(repo), plugin)
    assert "unknown" in record["reason"]


def test_repo_version_non_string_version_unknown(tmp_path):
    repo = tmp_path / "repo"
    path = repo / "plugins" / "superheroes" / ".claude-plugin" / "plugin.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"name": "superheroes", "version": 42}), encoding="utf-8")
    _copy_semantics_to(repo)
    plugin = _plugin_tree(tmp_path)
    record = version_skew.detect(str(repo), plugin)
    assert "unknown" in record["reason"]


def test_repo_version_unreadable_manifest_unknown_status_unchanged(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    plugin = _plugin_tree(tmp_path)
    record = version_skew.detect(str(repo), plugin)
    assert record["status"] == version_skew.STATUS_NOT_CHECKED
    assert record["detail"] == version_skew.DETAIL_NOT_SOURCE_REPO
