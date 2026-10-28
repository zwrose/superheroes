# plugins/superheroes/lib/tests/test_verify_required_c1l3.py
"""Code review needs a verify command (#2207 C1-L3 WO-A): ``review_code_config.resolve`` reports
``verifyRefusal`` exactly when no real verify command resolves, whichever way the project says so.

Strings are spelled out on purpose: a test that reaches them through the module constants stays
green under any value (rubric/bite-proof.md, external-contract constant).

Detector axes (bite-proof):
- E1 test_no_command_in_core_* — core records no command: refusal set, command "none"
- E2 test_legacy_profile_review_only_* — the legacy `mode: review-only` profile reads as no command
- E3 test_legacy_profile_unverified_* — the legacy `mode: unverified` profile reads as no command
- E4 test_core_none_in_any_case_* — case/whitespace `none` reads as no command
- E5 test_configured_command_* — a configured command yields no refusal
"""
import json
import os
import subprocess
import sys

import pytest

_LIB = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import core_md  # noqa: E402
import review_code_config  # noqa: E402

_REFUSAL = {
    "reason": "verify-command-required",
    "message": ("Code review is not available until a verify command is set. Code review needs a "
                "command that verifies this project's code; set one with /superheroes:configure."),
}


@pytest.fixture(autouse=True)
def _pin_git(monkeypatch):
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def _repo(tmp_path):
    repo = tmp_path / "proj"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    return str(repo)


def _write_core(repo, verify):
    d = os.path.join(repo, ".claude", "superheroes")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "core.md"), "w") as fh:
        fh.write(core_md.render_core(
            {"verifyCommand": verify, "stackTags": ["python"], "threatModel": "x", "patterns": ""},
            "confirmed", "2026-06-26", "2026-06-26"))


def _write_legacy_profile(repo, verify_section):
    prof = os.path.join(repo, ".claude", "review-profile.md")
    os.makedirs(os.path.dirname(prof), exist_ok=True)
    with open(prof, "w") as fh:
        fh.write("## Threat model\nsingle-user\n\n## Verify\n%s\n" % verify_section)


def _resolve(tmp_path, repo):
    return review_code_config.resolve(repo, root=str(tmp_path / "store"))


def test_refusal_constants_are_pinned():
    assert review_code_config.VERIFY_REFUSAL_REASON == "verify-command-required"
    assert review_code_config.VERIFY_REFUSAL_MESSAGE == (
        "Code review is not available until a verify command is set. Code review needs a command "
        "that verifies this project's code; set one with /superheroes:configure.")


def test_no_command_in_core_is_refused(tmp_path):
    repo = _repo(tmp_path)
    _write_core(repo, None)
    out = _resolve(tmp_path, repo)
    assert out["verifyRefusal"] == _REFUSAL
    assert out["verifyCommand"] == "none"
    assert out["calibrationRefusal"] is None
    assert "verifyMode" not in out


def test_no_core_at_all_is_refused(tmp_path):
    repo = _repo(tmp_path)
    out = _resolve(tmp_path, repo)
    assert out["verifyRefusal"] == _REFUSAL
    assert out["verifyCommand"] == "none"


def test_legacy_profile_review_only_is_refused(tmp_path):
    repo = _repo(tmp_path)
    _write_legacy_profile(repo, "mode: review-only")
    out = _resolve(tmp_path, repo)
    assert out["verifyRefusal"] == _REFUSAL
    assert out["verifyCommand"] == "none"
    assert "verifyMode" not in out


def test_legacy_profile_unverified_is_refused(tmp_path):
    repo = _repo(tmp_path)
    _write_legacy_profile(repo, "mode: unverified")
    out = _resolve(tmp_path, repo)
    assert out["verifyRefusal"] == _REFUSAL
    assert out["verifyCommand"] == "none"
    assert "verifyMode" not in out


@pytest.mark.parametrize("section", [
    "mode: review-only\ncommand: make test",
    "command: make test\nmode: review-only",
    "mode: unverified\ncommand: make test",
    "command: make test\nmode: `unverified`",
    "mode: review-only # temporarily disabled\ncommand: make test",
    "command: make test\nmode: `unverified` # old opt-out",
])
def test_legacy_profile_retired_mode_with_retained_command_is_refused(tmp_path, section):
    repo = _repo(tmp_path)
    _write_legacy_profile(repo, section)
    out = _resolve(tmp_path, repo)
    assert out["verifyRefusal"] == _REFUSAL
    assert out["verifyCommand"] == "none"


@pytest.mark.parametrize("verify", ["NONE", "  none  ", "None"])
def test_core_none_in_any_case_is_refused(tmp_path, verify):
    repo = _repo(tmp_path)
    _write_core(repo, verify)
    out = _resolve(tmp_path, repo)
    assert out["verifyRefusal"] == _REFUSAL
    assert out["verifyCommand"] == "none"


def test_configured_command_is_not_refused(tmp_path):
    repo = _repo(tmp_path)
    _write_core(repo, "pytest -q")
    out = _resolve(tmp_path, repo)
    assert out["verifyRefusal"] is None
    assert out["verifyCommand"] == "pytest -q"


def test_configured_legacy_profile_command_is_not_refused(tmp_path):
    repo = _repo(tmp_path)
    _write_legacy_profile(repo, "command: make test")
    out = _resolve(tmp_path, repo)
    assert out["verifyRefusal"] is None
    assert out["verifyCommand"] == "make test"


def test_malformed_command_keeps_its_own_refusal_and_sets_verify_refusal(tmp_path):
    repo = _repo(tmp_path)
    _write_core(repo, "pytest -q")
    core_file = os.path.join(repo, ".claude", "superheroes", "core.md")
    text = open(core_file).read().replace('"verifyCommand": "pytest -q"', '"verifyCommand": 5')
    assert '"verifyCommand": 5' in text
    open(core_file, "w").write(text)
    out = _resolve(tmp_path, repo)
    assert out["calibrationRefusal"]["reason"] == "verify-command-malformed"
    assert out["verifyRefusal"] == _REFUSAL
    assert out["verifyCommand"] == "none"


@pytest.mark.parametrize("cmd,expected", [
    ("pytest -q", True),
    ("  pytest -q  ", True),
    ("none", False),
    ("NONE", False),
    ("  None  ", False),
    ("", False),
    ("   ", False),
    (None, False),
    (5, False),
    (["pytest"], False),
])
def test_verify_command_configured_predicate(cmd, expected):
    assert review_code_config.verify_command_configured(cmd) is expected


def test_cli_prints_the_refusal_for_a_project_with_no_verify_command(tmp_path):
    # the setup witness: a project set up with no verify command shows the owner this message
    repo = _repo(tmp_path)
    _write_core(repo, None)
    proc = subprocess.run(
        [sys.executable, "-B", os.path.join(_LIB, "review_code_config.py")],
        cwd=repo, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["verifyRefusal"]["message"] == _REFUSAL["message"]
    assert out["verifyRefusal"]["reason"] == "verify-command-required"
    assert out["verifyCommand"] == "none"
