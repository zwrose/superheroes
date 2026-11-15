"""#2502 WO-1 — a review session pins the calibration it read at start.

Fixtures use the default calibration store under a temp ``HOME`` (the layout ``calibration_read.resolved_paths``
resolves itself), so no reader is stubbed: a risk-area, engine-preference or residual edit written to that store
after a session is created must not reach it, and a session created afterwards must see it.

Bite-proof record: wo1_2502_calibration_pin
"""
import copy
import hashlib
import json
import os
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import calibration_pin  # noqa: E402
import calibration_read  # noqa: E402
import core_md  # noqa: E402
import engine_pref  # noqa: E402
import mode_registry  # noqa: E402
import round_driver as RD  # noqa: E402
import round_records as RR  # noqa: E402
import seat_map as SM  # noqa: E402

_PAYMENTS_FILE = "src/payments/charge.py"
_RISKY_DIFF = ("diff --git a/%s b/%s\n--- a/%s\n+++ b/%s\n@@ -1 +1 @@\n-old\n+new\n" % ((_PAYMENTS_FILE,) * 4))
_DOCS_DIFF = ("diff --git a/docs/readme.md b/docs/readme.md\n"
              "--- a/docs/readme.md\n+++ b/docs/readme.md\n@@ -1 +1 @@\n-old\n+new\n")
_SECRETS = {"name": "Secrets", "covers": ["secrets/*"], "why": "Holds keys.", "undo": "Hard: rotate the keys."}
_PAYMENTS = {"name": "Payments", "covers": ["src/payments/*"], "why": "Charges customers.",
             "undo": "Hard: a charge needs a refund."}
_LAYER_TEXT = "# Review crew\n\nPolicy version: 3\n\nThe layer rules for this project, original.\n"
_CLAUDE_TEXT = "# Project\n\nThe project rules, original wording.\n"


def _core_file(repo):
    return os.path.join(mode_registry.project_store_dir(repo), "config", "core.md")


def _layer_file(repo):
    return os.path.join(mode_registry.project_store_dir(repo), "config", "review-crew.md")


def _put(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def _write_core(repo, areas, reviewer="codex", residuals="Residual: original ruling."):
    facts = {"verifyCommand": "npm test", "stackTags": ["node"], "threatModel": "single-user",
             "patterns": "- x: a.ts:1", "enginePreferences": {"reviewer": reviewer},
             "ratifiedResiduals": residuals,
             "projectConfiguration": {core_md.RISK_AREAS_KEY: areas}}
    _put(_core_file(repo), core_md.render_core(facts, "confirmed", "2026-06-26", "2026-06-26"))


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    for var in ("SUPERHEROES_STORE_ROOT", "WORKHORSE_STORE_ROOT", "CLAUDE_CODE_REMOTE"):
        monkeypatch.delenv(var, raising=False)
    path = str(tmp_path / "repo")
    os.makedirs(path)
    subprocess.run(["git", "init", "-q", path], check=True)
    _write_core(path, [_SECRETS])
    _put(_layer_file(path), _LAYER_TEXT)
    _put(os.path.join(path, "CLAUDE.md"), _CLAUDE_TEXT)
    # no reader is stubbed: the driver's own resolution finds the store this fixture wrote
    assert calibration_read.resolved_paths(path) == (_core_file(path), _layer_file(path), None)
    return path


def _config(repo):
    return {"repoRoot": repo, "diff": _DOCS_DIFF,
            "seatMap": {"roster": list(SM.BASE_ROSTER), "laneBasis": {"floor": None}}}


def _session(tmp_path, name):
    folder = str(tmp_path / name)
    os.makedirs(folder)
    return folder


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _read_bytes(path):
    with open(path, "rb") as fh:
        return fh.read()


def test_a_mid_run_risk_area_edit_does_not_reach_a_running_session_but_the_next_one_sees_it(repo, tmp_path):
    # axis: a running session reads the calibration pinned at its start, never the live store
    state_a = RD.new_state(_config(repo), session_dir=_session(tmp_path, "a"))
    assert not state_a.get("terminal") and state_a["config"]["dimensions"] == ["code-reviewer", "test-role"]
    _write_core(repo, [_SECRETS, _PAYMENTS])
    unpinned = copy.deepcopy(state_a)
    unpinned.pop("calibrationPin")
    assert RD._reevaluate_lane_dimensions(unpinned, unpinned["config"], _RISKY_DIFF) is True  # the edit is live
    assert RD._reevaluate_lane_dimensions(state_a, state_a["config"], _RISKY_DIFF) is False
    assert not state_a.get("terminal")
    state_b = RD.new_state(_config(repo), session_dir=_session(tmp_path, "b"))
    assert RD._reevaluate_lane_dimensions(state_b, state_b["config"], _RISKY_DIFF) is True
    assert state_b["decisions"][-1]["kind"] == "lane-expanded-recompose"


def test_slice_security_reads_the_pinned_risk_areas(repo, tmp_path):
    # axis: a running session reads the calibration pinned at its start, never the live store
    pin_a = RD.new_state(_config(repo), session_dir=_session(tmp_path, "a"))["calibrationPin"]
    _write_core(repo, [_SECRETS, _PAYMENTS])
    pin_b = RD.new_state(_config(repo), session_dir=_session(tmp_path, "b"))["calibrationPin"]
    dims, parts = ["security-reviewer"], [{"file": _PAYMENTS_FILE}]
    assert RD._slice_security(dims, repo, parts, None, stored=pin_a["riskAreas"]) is False
    assert RD._slice_security(dims, repo, parts, None, stored=pin_b["riskAreas"]) is True
    assert RD._slice_security(dims, repo, parts) is True  # no pin: today's live read


def test_the_test_role_risk_areas_clause_reads_the_pin(repo, tmp_path, monkeypatch):
    # axis: a running session reads the calibration pinned at its start, never the live store
    # the changed paths are stubbed (no base/head commits needed); the risk areas themselves are the real read
    monkeypatch.setattr(RD, "_risk_areas_changed_paths", lambda *_a: ([_PAYMENTS_FILE], None))
    pin_a = RD.new_state(_config(repo), session_dir=_session(tmp_path, "a"))["calibrationPin"]
    _write_core(repo, [_SECRETS, _PAYMENTS])
    pinned = RD._risk_areas_text("test-role", repo, "base", "head", stored=pin_a["riskAreas"])
    assert pinned == "none of this project's risk areas"
    assert "Payments" in RD._risk_areas_text("test-role", repo, "base", "head")


def test_capture_copies_the_bytes_read_and_a_later_edit_leaves_the_copies_alone(repo, tmp_path):
    # axis: the pin holds a copy of the bytes read, never a link to the live path
    folder = _session(tmp_path, "a")
    originals = {"core": _read_bytes(_core_file(repo)), "layer": _read_bytes(_layer_file(repo)),
                 "claudeMd": _read_bytes(os.path.join(repo, "CLAUDE.md"))}
    pin = calibration_pin.capture(repo, folder)
    _write_core(repo, [_PAYMENTS], reviewer="claude")
    _put(_layer_file(repo), "edited layer\n")
    _put(os.path.join(repo, "CLAUDE.md"), "edited claude\n")
    names = {"core": "core.md", "layer": "review-crew.md", "claudeMd": "CLAUDE.md"}
    for label, entry in pin["files"].items():
        assert entry["path"].startswith(folder + os.sep), label
        assert entry["file"] == names[label]
        assert entry["sha256"] == _sha(originals[label])
        assert _read_bytes(entry["path"]) == originals[label]


def test_a_rendered_session_cites_the_pinned_copies_in_its_orders(repo, tmp_path):
    # the end-to-end half: `next` creates the session, renders the panel orders, and the orders name the copies
    folder = _session(tmp_path, "run")
    cfg = {"leg": "code", "vendors": ["claude", "codex"], "diff": _DOCS_DIFF, "repoRoot": repo,
           "fixerVendor": "claude", "verifyCommand": "none"}
    out = RD.cmd_next(folder, cfg)
    assert out["ok"], out
    ok, state = RD.load_state(folder)
    assert ok, state
    files = state["calibrationPin"]["files"]
    texts = []
    for root, _dirs, names in os.walk(RR.round_dir(folder, 1)):
        texts += [open(os.path.join(root, n), encoding="utf-8").read() for n in names if n.endswith(".md")]
    joined = "\n".join(texts)
    for key in ("core", "layer", "claudeMd"):
        assert files[key]["path"] in joined, key
    for live in (_core_file(repo), _layer_file(repo), os.path.join(repo, "CLAUDE.md")):
        assert live not in joined


def test_engine_preferences_are_pinned(repo, tmp_path):
    # axis: a running session reads the calibration pinned at its start, never the live store
    before = engine_pref.load_engine_prefs(repo)
    state_a = RD.new_state(_config(repo), session_dir=_session(tmp_path, "a"))
    assert state_a["calibrationPin"]["enginePrefs"] == before  # the pinned copy normalises as the live read does
    assert RD._reviewer_engine_vendor(repo, state=state_a) == ("codex", "configured")
    _write_core(repo, [_SECRETS], reviewer="claude")
    assert RD._reviewer_engine_vendor(repo, state=state_a) == ("codex", "configured")
    assert RD._reviewer_engine_vendor(repo) == ("claude", "configured")


def test_store_mode_ratified_residuals_are_pinned(repo, tmp_path):
    # axis: a running session reads the calibration pinned at its start, never the live store
    state_a = RD.new_state(_config(repo), session_dir=_session(tmp_path, "a"))
    assert state_a["calibrationPin"]["residuals"]["storage"] == "store"
    _write_core(repo, [_SECRETS], residuals="Residual: edited ruling.")
    assert state_a["calibrationPin"]["residuals"]["text"] == "Residual: original ruling."
    sources = RD._decision_sources(state_a)
    assert sources["residualText"] == "Residual: original ruling."
    assert sources["residualSource"] == "calibration store"
    unpinned = copy.deepcopy(state_a)
    unpinned.pop("calibrationPin")
    assert RD._decision_sources(unpinned)["residualText"] == "Residual: edited ruling."


def test_a_copy_that_cannot_be_written_is_unreadable_and_never_falls_back_to_the_live_path(repo, tmp_path):
    # a regular file where the core copy's folder belongs makes only that copy unwritable
    folder = _session(tmp_path, "a")
    os.makedirs(os.path.join(folder, calibration_pin.PIN_DIR))
    _put(os.path.join(folder, calibration_pin.PIN_DIR, "core"), "in the way")
    live = _core_file(repo)
    pin = calibration_pin.capture(repo, folder)
    entry = pin["files"]["core"]
    assert entry["reason"] == calibration_pin.REASON_UNREADABLE and entry["path"] is None
    assert entry["source"] == live  # provenance only
    assert live not in entry["detail"] and repo not in entry["detail"]
    assert pin["files"]["layer"]["path"]  # the other files pinned normally
    text = RD._pinned_path_text(pin, "core", "Core", repo)
    assert "not pinned" in text and live not in text
    model, failure = RD._pinned_threat_model(pin)
    assert model == "" and "not pinned" in failure and live not in failure
    assert pin["riskAreas"]["reason"] == core_md.RISK_AREAS_REASON_UNREADABLE
    assert pin["enginePrefs"]["readError"].startswith("calibration-pin:")
    assert pin["residuals"]["failure"].startswith("calibration-pin:")
    assert live not in json.dumps({k: v for k, v in pin.items() if k != "files"})


def test_a_second_capture_returns_the_first_unchanged(repo, tmp_path):
    folder = _session(tmp_path, "a")
    first = calibration_pin.capture(repo, folder)
    _write_core(repo, [_PAYMENTS], reviewer="claude", residuals="Residual: edited ruling.")
    second = calibration_pin.capture(repo, folder)
    assert second == first
    assert _sha(_read_bytes(second["files"]["core"]["path"])) == first["files"]["core"]["sha256"]


def test_a_state_made_without_a_session_folder_carries_no_pin(repo):
    assert "calibrationPin" not in RD.new_state(_config(repo))


def test_stamp_recognises_the_pinned_copies(repo, tmp_path):
    pin = calibration_pin.capture(repo, _session(tmp_path, "a"))
    copy_path = pin["files"]["core"]["path"]
    got = calibration_read.stamp(repo, "Read the core calibration at %s before you start." % copy_path)
    assert [e["label"] for e in got] == ["core"]
    assert got[0]["path"] == copy_path and got[0]["file"] == "core.md"
    assert got[0]["sha256"] == _sha(_read_bytes(copy_path))
    # an order naming only the live path is stamped from the live file, as before
    live = calibration_read.stamp(repo, "Read %s" % _core_file(repo))
    assert live[0]["path"] == _core_file(repo)


@pytest.mark.parametrize("text", ["not json", "[1]", json.dumps({"schema": "other/1"})])
def test_a_corrupt_manifest_loads_as_none(tmp_path, text):
    folder = str(tmp_path / "s")
    os.makedirs(os.path.join(folder, calibration_pin.PIN_DIR))
    _put(os.path.join(folder, calibration_pin.PIN_DIR, calibration_pin.MANIFEST), text)
    assert calibration_pin.load(folder) is None
    assert calibration_pin.manifest_for(os.path.join(folder, calibration_pin.PIN_DIR, "core", "core.md")) is None


def test_absent_calibration_pins_as_absent_with_todays_text(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    for var in ("SUPERHEROES_STORE_ROOT", "WORKHORSE_STORE_ROOT"):
        monkeypatch.delenv(var, raising=False)
    bare = str(tmp_path / "bare")
    os.makedirs(bare)
    subprocess.run(["git", "init", "-q", bare], check=True)
    pin = calibration_pin.capture(bare, _session(tmp_path, "a"))
    assert {e["reason"] for e in pin["files"].values()} == {calibration_pin.REASON_ABSENT}
    assert pin["riskAreas"]["reason"] == "core-md-absent"
    assert RD._pinned_path_text(pin, "claudeMd", "CLAUDE.md", bare) == RD._claude_md_path_placeholder(bare)
    assert RD._pinned_path_text(pin, "core", "Core", bare) == RD._calibration_path_placeholder(None, "Core")
    assert json.loads(json.dumps(pin)) == pin
