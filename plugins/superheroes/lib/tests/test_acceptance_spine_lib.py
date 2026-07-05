# plugins/superheroes/lib/tests/test_acceptance_spine_lib.py
#
# #235 pre-release gate: `--spine-lib` pins the spine UNDER TEST (merged-but-unreleased
# main) instead of the installed plugin, so the fixture run can gate main BEFORE a
# release is cut. These tests cover the deps/run/result layers deterministically — no
# live run: bad-override refusals (nothing materialized), spine provenance in the record
# + report, and phase-source following the override.
import hashlib
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import acceptance_deps as deps          # noqa: E402
import acceptance_result as result      # noqa: E402


def _valid_spine_lib(root, phases="['alpha', 'beta', 'gamma']", bundle=b"// bundle bytes\n",
                     version=None):
    """Materialize a well-formed override lib dir: a committed bundle + a showrunner.js
    carrying a (possibly doctored) PHASES literal, optionally a version.txt."""
    lib = root / "lib"
    lib.mkdir()
    (lib / "showrunner.bundle.js").write_bytes(bundle)
    (lib / "showrunner.js").write_text("const PHASES = %s\n" % phases, encoding="utf-8")
    if version is not None:
        (lib / "version.txt").write_text(version, encoding="utf-8")
    return lib


# --- refusal cases (UFR-7 pre-launch; nothing materialized) ---------------------------

def test_spine_lib_refusal_missing_directory_names_the_path(tmp_path):
    missing = str(tmp_path / "nope")
    reason = deps._spine_lib_refusal(missing)
    assert reason is not None
    assert missing in reason
    assert "does not exist" in reason


def test_spine_lib_refusal_missing_bundle_names_the_path(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "showrunner.js").write_text("const PHASES = ['x']\n", encoding="utf-8")
    reason = deps._spine_lib_refusal(str(lib))
    assert reason is not None
    assert os.path.join(str(lib), "showrunner.bundle.js") in reason


def test_spine_lib_refusal_missing_showrunner_js_names_the_path(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "showrunner.bundle.js").write_bytes(b"// bundle\n")
    reason = deps._spine_lib_refusal(str(lib))
    assert reason is not None
    assert os.path.join(str(lib), "showrunner.js") in reason


def test_spine_lib_refusal_none_when_well_formed(tmp_path):
    lib = _valid_spine_lib(tmp_path)
    assert deps._spine_lib_refusal(str(lib)) is None


def test_spine_lib_unset_never_refuses():
    assert deps._spine_lib_refusal(None) is None


def test_preflight_refuses_bad_override_before_touching_fixture(monkeypatch, tmp_path):
    # A bad override must refuse FIRST — before the fixture drift check reads phases or
    # the live probe runs — naming the offending path, and nothing is created.
    import acceptance_fixture
    import preflight

    def _boom(*a, **k):
        raise AssertionError("must not run after a bad-override refusal")

    monkeypatch.setattr(acceptance_fixture, "drift_check", _boom)
    monkeypatch.setattr(preflight, "probe", _boom)

    fixture = tmp_path / "fixture"
    fixture.mkdir()
    (fixture / "target.txt").write_text("x\n", encoding="utf-8")
    missing = str(tmp_path / "no-spine")

    result_dict = deps.real_preflight_ok(str(fixture), "root", spine_lib=missing)("wi")
    assert result_dict["ok"] is False
    assert missing in result_dict["reason"]
    # nothing materialized: the preflight decider only os.path-checks, so no dirs/files
    # beyond the caller-provided fixture exist.
    assert list(tmp_path.iterdir()) == [fixture]


# --- provenance (record + report carry lib path + bundle hash) ------------------------

def test_spine_provenance_seam_reports_lib_path_hash_and_version(tmp_path):
    body = b"// the spine under test\n"
    lib = _valid_spine_lib(tmp_path, bundle=body, version="0.11.0\n")
    prov = deps.real_spine_provenance(str(lib))()
    assert prov["lib_path"] == str(lib)
    assert prov["bundle_sha256"] == hashlib.sha256(body).hexdigest()
    assert prov["version"] == "0.11.0"


def test_spine_provenance_version_none_when_absent(tmp_path):
    lib = _valid_spine_lib(tmp_path)  # no version.txt
    prov = deps.real_spine_provenance(str(lib))()
    assert prov["version"] is None
    assert prov["bundle_sha256"] is not None


def test_spine_provenance_none_when_no_override():
    assert deps.real_spine_provenance(None)() is None


def test_report_renders_spine_under_test_section(tmp_path):
    report = result.render_report({
        "verdict": "pass",
        "reason": "clean run",
        "record_path": "/rec.json",
        "cleaned_up": [],
        "left_behind": [],
        "spine_provenance": {"lib_path": "/repo/plugins/superheroes/lib",
                             "bundle_sha256": "deadbeef", "version": "0.11.0"},
    })
    assert "Spine under test" in report
    assert "/repo/plugins/superheroes/lib" in report
    assert "deadbeef" in report
    assert "0.11.0" in report


def test_report_omits_spine_section_by_default():
    report = result.render_report({
        "verdict": "pass", "reason": "clean run", "record_path": "/rec.json",
        "cleaned_up": [], "left_behind": [],
    })
    assert "Spine under test" not in report


# --- phase source follows the override ------------------------------------------------

def test_expected_phases_follow_the_override(tmp_path):
    # A doctored showrunner.js in the override lib changes expected_phases...
    lib = _valid_spine_lib(tmp_path, phases="['alpha', 'beta', 'gamma']")
    assert deps.real_expected_phases(spine_lib=str(lib))() == ["alpha", "beta", "gamma"]
    # ...while the default path still reads the harness's own sibling showrunner.js
    # (the real pipeline, which is decidedly not the doctored ['alpha', 'beta', 'gamma']).
    default_phases = deps.real_expected_phases()()
    assert default_phases != ["alpha", "beta", "gamma"]
    assert "plan" in default_phases and "ship" in default_phases


def test_preflight_reads_phases_from_the_override_tree(monkeypatch, tmp_path):
    # The drift check must be handed the OVERRIDE's phases, not the sibling default's.
    import acceptance_fixture
    import preflight

    seen = {}

    def _capture_drift(fixture, phases, target_exists):
        seen["phases"] = phases
        return {"ok": True, "reason": "fixture ok"}

    monkeypatch.setattr(acceptance_fixture, "drift_check", _capture_drift)
    monkeypatch.setattr(preflight, "probe",
                        lambda work_item, root: {"gh": {"ok": True}, "config_resolves": True})

    fixture = tmp_path / "fixture"
    fixture.mkdir()
    (fixture / "target.txt").write_text("x\n", encoding="utf-8")
    lib = _valid_spine_lib(tmp_path, phases="['solo']")

    out = deps.real_preflight_ok(str(fixture), "root", spine_lib=str(lib))("wi")
    assert out["ok"] is True
    assert seen["phases"] == ["solo"]
