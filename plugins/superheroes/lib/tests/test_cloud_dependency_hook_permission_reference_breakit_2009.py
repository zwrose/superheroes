"""Credentials: an environment-reference permission must not prevent hook installation."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import cloud_dependency_hook as hook


def test_reference_printf_permission_allows_hook_installation(tmp_path):
    # axis: credential-free permission text keeps its printf/reference exemption in JSON settings.
    repo = tmp_path / "repo"
    repo.mkdir()
    settings = repo / hook.SETTINGS_REL
    settings.parent.mkdir(parents=True)
    command = "printf 'AWS_SECRET_ACCESS_KEY=%s\\n' \"$AWS_SECRET_ACCESS_KEY\" > .env"
    permissions = {"allow": ["Bash(" + command + ")"]}
    settings.write_text(json.dumps({"permissions": permissions}), encoding="utf-8")

    result = hook.sync(str(repo), ["npm ci"], [], True)

    assert result["action"] == "written", result
    assert (repo / hook.SCRIPT_REL).is_file()
    assert json.loads(settings.read_text(encoding="utf-8"))["permissions"] == permissions


def test_literal_credential_in_permission_is_still_refused(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    settings = repo / hook.SETTINGS_REL
    settings.parent.mkdir(parents=True)
    command = "export OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwxyz0123456789"
    permissions = {"allow": ["Bash(" + command + ":*)"]}
    settings.write_text(json.dumps({"permissions": permissions}), encoding="utf-8")

    result = hook.sync(str(repo), ["npm ci"], [], True)

    assert result["action"] == "refused", result
    assert result["reason"] == "settings-secret-shaped"
