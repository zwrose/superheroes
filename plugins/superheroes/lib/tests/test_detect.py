import json

import detect


def test_dev_server_from_package_json(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"scripts": {"dev": "vite"}}))
    r = detect.detect_dev_server(str(tmp_path))
    assert r["command"] == "npm run dev" and r["source"] == "package.json"
    assert r["script"] == "dev"
    assert r["argv"] == ["npm", "run", "dev"]


def test_dev_server_profile_override_wins(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"scripts": {"dev": "vite"}}))
    r = detect.detect_dev_server(str(tmp_path), profile={"devCommand": "make serve"})
    assert r["command"] == "make serve" and r["source"] == "profile"


def test_dev_server_none_is_noted(tmp_path):
    r = detect.detect_dev_server(str(tmp_path))
    assert r["command"] is None and "skipped" in r["note"]


def test_dev_server_malformed_package_json_does_not_raise(tmp_path):
    (tmp_path / "package.json").write_text("{ not json")
    r = detect.detect_dev_server(str(tmp_path))
    assert r["command"] is None


def test_ci_detects_github_actions(tmp_path):
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "ci.yml").write_text("name: CI\n")
    assert detect.detect_ci(str(tmp_path))["provider"] == "github-actions"


def test_ci_none_is_noted(tmp_path):
    r = detect.detect_ci(str(tmp_path))
    assert r["provider"] is None and r["note"] == "CI not detected"


def test_dev_server_non_dict_package_json_does_not_raise(tmp_path):
    # valid JSON whose root is NOT an object (array / scalar) must not crash the
    # detector — the never-raises invariant covers well-formed-but-unexpected shapes too.
    (tmp_path / "package.json").write_text("[1, 2, 3]")
    r = detect.detect_dev_server(str(tmp_path))
    assert r["command"] is None and r["source"] == "none"


def test_dev_server_blank_profile_command_falls_through(tmp_path):
    # a whitespace-only devCommand is not a real command -> fall through to detection/none
    (tmp_path / "package.json").write_text(json.dumps({"scripts": {"dev": "vite"}}))
    r = detect.detect_dev_server(str(tmp_path), profile={"devCommand": "   "})
    assert r["source"] == "package.json" and r["command"] == "npm run dev"


def test_dev_server_package_unsafe_script_name_has_no_argv(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"scripts": {"dev;bad": "vite"}}))
    r = detect.detect_dev_server(str(tmp_path), profile=None)

    assert r["source"] == "none"
    assert r["command"] is None
